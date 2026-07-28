"""Renderer-facing typed scene graph for future editable PPTX output.

SceneDeck uses presentation inches as its only coordinate system. The origin is
the top-left corner of the slide, ``x`` grows to the right, and ``y`` grows
down. Rectangles use ``x``, ``y``, ``width``, and ``height`` in inches so they
can map directly to python-pptx ``Inches(...)`` calls in later renderer PRs.

This module is intentionally a scaffold. It does not replace Blueprint or the
current SlideIR boundary, and it does not contain layout or rendering business
logic. ``Group`` is logical metadata only in this PR; it is not a requirement
that the current PPTX renderer emit native grouped shapes.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCENE_COORDINATE_SYSTEM = "inches-top-left"
SCENE_SCHEMA_NAME = "scene_deck"
SCENE_SCHEMA_VERSION = "0.1"
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class SceneModel(BaseModel):
    """Base model for strict renderer-facing scene objects."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Rect(SceneModel):
    """Axis-aligned rectangle in presentation inches."""

    x: float
    y: float
    width: float
    height: float

    @field_validator("x", "y")
    @classmethod
    def _validate_origin(cls, value: float) -> float:
        if value < 0:
            raise ValueError("coordinates must be non-negative presentation inches")
        return value

    @field_validator("width", "height")
    @classmethod
    def _validate_size(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("width and height must be positive presentation inches")
        return value

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height


class ThemeRef(SceneModel):
    """Reference to a design-system token, with an optional fixed fallback."""

    token: str
    fallback_hex: str | None = None

    @field_validator("token")
    @classmethod
    def _validate_token(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("theme token is required")
        return value

    @field_validator("fallback_hex")
    @classmethod
    def _validate_fallback_hex(cls, value: str | None) -> str | None:
        if value is not None and not _HEX_COLOR_RE.match(value):
            raise ValueError("fallback_hex must be '#RRGGBB'")
        return value


class FitPolicy(SceneModel):
    """Renderer policy for content that does not fit its assigned bounds."""

    mode: Literal["none", "wrap", "shrink_text", "truncate", "fail"] = "fail"
    min_font_size_pt: float | None = None
    overflow_action: Literal["warn", "fail"] = "fail"

    @field_validator("min_font_size_pt")
    @classmethod
    def _validate_min_font_size(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("min_font_size_pt must be positive when provided")
        return value


class TextRun(SceneModel):
    """Editable text run that a renderer can map to PowerPoint run styling."""

    text: str
    font_token: str | None = None
    size_pt: float | None = None
    bold: bool = False
    italic: bool = False
    color: ThemeRef | None = None

    @field_validator("size_pt")
    @classmethod
    def _validate_size_pt(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("size_pt must be positive when provided")
        return value


class BulletItem(SceneModel):
    """One editable bullet paragraph with an explicit nesting level."""

    runs: list[TextRun] = Field(min_length=1)
    level: int = 0
    bullet_style: Literal["bullet", "number", "none"] = "bullet"

    @field_validator("level")
    @classmethod
    def _validate_level(cls, value: int) -> int:
        if value < 0:
            raise ValueError("bullet level must be non-negative")
        return value


class TextBox(SceneModel):
    kind: Literal["text_box"] = "text_box"
    object_id: str
    role: str
    bounds: Rect
    z_order: int
    reading_order: int
    runs: list[TextRun] = Field(default_factory=list)
    bullet_list: list[BulletItem] = Field(default_factory=list)
    fit: FitPolicy = Field(default_factory=FitPolicy)
    fill: ThemeRef | None = None

    @model_validator(mode="after")
    def _require_text_content(self) -> "TextBox":
        if not self.runs and not self.bullet_list:
            raise ValueError("TextBox requires runs or bullet_list")
        return self


class Shape(SceneModel):
    kind: Literal["shape"] = "shape"
    object_id: str
    role: str | None = None
    shape_type: str
    bounds: Rect
    z_order: int
    fill: ThemeRef | None = None
    stroke: ThemeRef | None = None
    radius: float | None = None

    @field_validator("radius")
    @classmethod
    def _validate_radius(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("radius must be non-negative")
        return value


class ImageCrop(SceneModel):
    """Image placement and crop/mask semantics.

    Crop offsets are normalized fractions of the source image. A value of 0.1
    means crop 10% from that edge before fitting into the slide bounds.
    """

    mode: Literal["contain", "cover", "crop"] = "contain"
    crop_left: float = 0.0
    crop_top: float = 0.0
    crop_right: float = 0.0
    crop_bottom: float = 0.0
    mask: Literal["rect", "rounded_rect", "circle"] = "rect"

    @field_validator("crop_left", "crop_top", "crop_right", "crop_bottom")
    @classmethod
    def _validate_crop_fraction(cls, value: float) -> float:
        if value < 0 or value >= 1:
            raise ValueError("crop fractions must be in the range [0, 1)")
        return value

    @model_validator(mode="after")
    def _validate_crop_total(self) -> "ImageCrop":
        if self.crop_left + self.crop_right >= 1:
            raise ValueError("horizontal crop fractions must leave visible image content")
        if self.crop_top + self.crop_bottom >= 1:
            raise ValueError("vertical crop fractions must leave visible image content")
        return self


class ImageObject(SceneModel):
    kind: Literal["image"] = "image"
    object_id: str
    asset_id: str
    source_path: str | None = None
    bounds: Rect
    z_order: int
    crop: ImageCrop = Field(default_factory=ImageCrop)
    alt_text: str | None = None


class TableCell(SceneModel):
    runs: list[TextRun] = Field(min_length=1)
    fill: ThemeRef | None = None
    align: Literal["left", "center", "right"] = "left"


class NativeTable(SceneModel):
    kind: Literal["native_table"] = "native_table"
    object_id: str
    bounds: Rect
    z_order: int
    headers: list[TableCell] = Field(min_length=1)
    rows: list[list[TableCell]] = Field(default_factory=list)
    column_widths: list[float] | None = None
    fit: FitPolicy = Field(default_factory=FitPolicy)

    @model_validator(mode="after")
    def _validate_table_shape(self) -> "NativeTable":
        column_count = len(self.headers)
        for row in self.rows:
            if len(row) != column_count:
                raise ValueError("all table rows must match header column count")
        if self.column_widths is not None:
            if len(self.column_widths) != column_count:
                raise ValueError("column_widths must match header column count")
            if any(width <= 0 for width in self.column_widths):
                raise ValueError("column_widths must be positive presentation inches")
        return self


class ChartSeries(SceneModel):
    series_id: str
    label: str
    values: list[float] = Field(min_length=1)
    color: ThemeRef | None = None


class NativeChart(SceneModel):
    kind: Literal["native_chart"] = "native_chart"
    object_id: str
    chart_type: Literal["bar", "column", "line", "scatter"]
    bounds: Rect
    z_order: int
    categories: list[str] = Field(min_length=1)
    series: list[ChartSeries] = Field(min_length=1)
    theme: str | None = None

    @model_validator(mode="after")
    def _validate_chart_shape(self) -> "NativeChart":
        category_count = len(self.categories)
        for item in self.series:
            if len(item.values) != category_count:
                raise ValueError("chart series values must match category count")
        return self


class DividerLine(SceneModel):
    kind: Literal["divider"] = "divider"
    object_id: str
    x1: float
    y1: float
    x2: float
    y2: float
    z_order: int
    stroke: ThemeRef
    width_pt: float = 1.0

    @field_validator("x1", "y1", "x2", "y2")
    @classmethod
    def _validate_line_coordinate(cls, value: float) -> float:
        if value < 0:
            raise ValueError("line coordinates must be non-negative presentation inches")
        return value

    @field_validator("width_pt")
    @classmethod
    def _validate_width_pt(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("width_pt must be positive")
        return value


class Callout(SceneModel):
    kind: Literal["callout"] = "callout"
    object_id: str
    bounds: Rect
    z_order: int
    reading_order: int
    title: TextRun | None = None
    body: list[TextRun] = Field(min_length=1)
    accent: ThemeRef | None = None
    fit: FitPolicy = Field(default_factory=FitPolicy)


class Group(SceneModel):
    """Logical grouping metadata; native PPT grouping is deferred."""

    kind: Literal["group"] = "group"
    object_id: str
    bounds: Rect
    z_order: int
    children: list[str] = Field(min_length=1)


SceneObject = Annotated[
    TextBox | Shape | ImageObject | NativeTable | NativeChart | DividerLine | Callout | Group,
    Field(discriminator="kind"),
]
MotifObject = Annotated[Shape | DividerLine, Field(discriminator="kind")]


class BackgroundLayer(SceneModel):
    fill: ThemeRef
    motifs: list[MotifObject] = Field(default_factory=list)


class SceneSlide(SceneModel):
    slide_id: str
    slide_number: int
    layout_family: str
    slide_role: str | None = None
    visual_type: str | None = None
    deck_mode: str | None = None
    layout_pattern_id: str | None = None
    background: BackgroundLayer
    objects: list[SceneObject] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("slide_number")
    @classmethod
    def _validate_slide_number(cls, value: int) -> int:
        if value < 1:
            raise ValueError("slide_number must be positive")
        return value

    @model_validator(mode="after")
    def _validate_unique_object_ids(self) -> "SceneSlide":
        object_ids = [item.object_id for item in self.objects]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("SceneSlide object_id values must be unique")
        known_ids = set(object_ids)
        for item in self.objects:
            if isinstance(item, Group):
                missing = [child for child in item.children if child not in known_ids]
                if missing:
                    raise ValueError(f"Group references unknown child object ids: {missing}")
        return self


class SceneDeck(SceneModel):
    schema_name: Literal["scene_deck"] = SCENE_SCHEMA_NAME
    schema_version: str = SCENE_SCHEMA_VERSION
    coordinate_system: Literal["inches-top-left"] = SCENE_COORDINATE_SYSTEM
    deck_id: str
    deck_title: str
    slide_width: float = 13.333
    slide_height: float = 7.5
    theme_tokens: dict[str, str] = Field(default_factory=dict)
    slides: list[SceneSlide] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("slide_width", "slide_height")
    @classmethod
    def _validate_slide_size(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("slide dimensions must be positive presentation inches")
        return value

    @field_validator("theme_tokens")
    @classmethod
    def _validate_theme_tokens(cls, value: dict[str, str]) -> dict[str, str]:
        for token, color in value.items():
            if not token.strip():
                raise ValueError("theme token names must be non-empty")
            if not _HEX_COLOR_RE.match(color):
                raise ValueError("theme token values must be '#RRGGBB'")
        return value

    @model_validator(mode="after")
    def _validate_slide_bounds(self) -> "SceneDeck":
        for slide in self.slides:
            for item in slide.objects:
                bounds = getattr(item, "bounds", None)
                if isinstance(bounds, Rect) and (bounds.right > self.slide_width or bounds.bottom > self.slide_height):
                    raise ValueError(f"{item.object_id} exceeds slide bounds")
        return self

    def to_stable_payload(self) -> dict[str, Any]:
        return scene_deck_to_stable_payload(self)

    def to_stable_json(self) -> str:
        return scene_deck_to_stable_json(self)

    def structural_hash(self) -> str:
        return scene_deck_structural_hash(self)


def _normalize_for_stable_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_for_stable_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize_for_stable_json(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("SceneDeck cannot serialize non-finite floats")
        normalized = round(value, 6)
        return 0.0 if normalized == 0 else normalized
    return value


def scene_deck_to_stable_payload(scene_deck: SceneDeck) -> dict[str, Any]:
    """Return a normalized JSON-compatible payload for deterministic tests."""

    payload = scene_deck.model_dump(mode="json", exclude_none=True)
    return _normalize_for_stable_json(payload)


def scene_deck_to_stable_json(scene_deck: SceneDeck) -> str:
    """Serialize a SceneDeck using stable key ordering and compact separators."""

    return json.dumps(scene_deck_to_stable_payload(scene_deck), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def scene_deck_structural_hash(scene_deck: SceneDeck) -> str:
    """Hash the normalized SceneDeck structure for future determinism checks."""

    stable_json = scene_deck_to_stable_json(scene_deck)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()
