from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal

from pptx.dml.color import RGBColor
from pydantic import BaseModel, ConfigDict, Field

from ..slide_scene import ThemeRef


SceneCompileWarningCode = Literal[
    "unsupported_scene_object",
    "unsupported_background_motif",
    "unsupported_slide_background",
    "missing_image_source_path",
    "missing_image_asset",
    "fit_policy_not_enforced",
    "unsupported_bullet_style",
    "unsupported_image_mask",
    "table_column_widths_normalized",
    "unsupported_chart_type",
    "unsupported_shape_type",
    "theme_token_missing",
    "theme_token_invalid",
    "font_token_missing",
    "font_token_unavailable",
    "spacing_token_missing",
    "color_fallback_used",
    "stroke_style_fallback_used",
    "fill_style_fallback_used",
    "text_style_fallback_used",
    "unsupported_opacity",
    "unsupported_font_feature",
    "style_token_alias_used",
    "style_token_alias_ambiguous",
    "style_token_alias_deprecated",
    "style_token_context_required",
    "style_token_normalized",
    "style_token_not_in_canonical_vocabulary",
]
SceneCompileSeverity = Literal["warning", "error"]
SCENE_TRACE_NAME_MAX = 255
TEXT_ROLE_DEFAULTS: dict[str, tuple[str, float, bool]] = {
    "title": ("title", 24.0, True),
    "claim": ("body", 16.0, True),
    "main-message": ("body", 14.0, False),
    "caption": ("caption", 9.0, False),
    "footer": ("caption", 9.0, False),
    "body": ("body", 11.0, False),
}
TEXT_FONT_NAMES: dict[str, str] = {
    "title": "Aptos Display",
    "body": "Aptos",
    "caption": "Aptos",
}


class RendererModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SceneCompileWarning(RendererModel):
    code: SceneCompileWarningCode
    severity: SceneCompileSeverity
    slide_number: int
    slide_id: str
    object_id: str | None = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


def append_warning(
    warnings: list[SceneCompileWarning],
    *,
    code: SceneCompileWarningCode,
    severity: SceneCompileSeverity,
    slide_number: int,
    slide_id: str,
    object_id: str | None,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    warnings.append(
        SceneCompileWarning(
            code=code,
            severity=severity,
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=object_id,
            message=message,
            details=details or {},
        )
    )


def warning_sort_key(item: SceneCompileWarning) -> tuple[int, str, str, str]:
    return (item.slide_number, item.object_id or "", item.code, item.message)


def hex_to_rgb(hex_color: str) -> RGBColor:
    value = hex_color.lstrip("#")
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def resolve_theme_color(theme_tokens: dict[str, str], ref: ThemeRef | None, default_hex: str) -> RGBColor:
    if ref is None:
        return hex_to_rgb(default_hex)
    hex_color = theme_tokens.get(ref.token, ref.fallback_hex or default_hex)
    return hex_to_rgb(hex_color)


def resolve_scene_path(path_text: str | None, *, root: Path | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    if path.is_absolute():
        return path
    if root is not None:
        return (root / path).resolve()
    return path.resolve()


def sanitize_filename_component(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in value.strip())
    safe = safe.strip("-")
    return safe or "object"


def stable_scene_shape_name(prefix: str, object_id: str, used_names: set[str]) -> str:
    base = f"scene:{prefix}:{object_id}"
    candidate = _truncate_trace_name(base)
    suffix_index = 2
    while candidate in used_names:
        candidate = _truncate_trace_name(f"{base}:{suffix_index}")
        suffix_index += 1
    used_names.add(candidate)
    return candidate


def scene_text_role_defaults(role: str) -> tuple[str, float, bool]:
    return TEXT_ROLE_DEFAULTS.get(role, ("body", 11.0, False))


def scene_font_name(font_token: str) -> str:
    return TEXT_FONT_NAMES.get(font_token, TEXT_FONT_NAMES["body"])


def _truncate_trace_name(value: str) -> str:
    if len(value) <= SCENE_TRACE_NAME_MAX:
        return value
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    head = value[: SCENE_TRACE_NAME_MAX - len(digest) - 1]
    return f"{head}:{digest}"


def set_shape_alt_text(shape: Any, alt_text: str | None) -> None:
    if not alt_text:
        return
    element = getattr(shape, "_element", None)
    if element is None:
        return
    for container_name in ("nvPicPr", "nvSpPr", "nvGraphicFramePr", "nvGrpSpPr"):
        container = getattr(element, container_name, None)
        c_nv_pr = getattr(container, "cNvPr", None) if container is not None else None
        if c_nv_pr is not None:
            c_nv_pr.set("descr", alt_text)
            break
