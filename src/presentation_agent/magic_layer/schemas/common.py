from __future__ import annotations

import json
from pathlib import Path
from typing import Any


NATIVE_TARGETS = {
    "ppt_text_box",
    "ppt_shape",
    "ppt_group",
    "svg_vector",
    "native_chart",
    "native_table",
    "editable_shape_chart",
    "editable_shape_grid_table",
    "editable_timeline",
    "editable_matrix",
    "editable_roadmap",
    "replaceable_image_frame",
    "suppression_shape",
    "explicit_reject",
}
RASTER_TARGETS = {"bounded_raster", "smart_object_like_image", "raster_image"}
TEXT_TOKENS = {"text", "title", "subtitle", "body", "label", "caption", "footer", "source"}
STRUCTURED_TOKENS = {"chart", "table", "timeline", "matrix", "roadmap"}


def load_json(value: dict[str, Any] | str | Path | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    path = Path(value)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def bbox_valid(bbox: Any) -> bool:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return False
    if not all(isinstance(value, (int, float)) for value in bbox):
        return False
    x, y, w, h = [float(value) for value in bbox]
    return x >= 0 and y >= 0 and w > 0 and h > 0 and x + w <= 1.000001 and y + h <= 1.000001


def is_full_slide_bbox(bbox: Any, threshold: float = 0.95) -> bool:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return False
    x, y, w, h = [float(value) for value in bbox]
    return x <= 0.025 and y <= 0.025 and w >= threshold and h >= threshold


def duplicate_ids(items: list[dict[str, Any]], key: str) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        value = str(item.get(key, ""))
        if not value:
            continue
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def role_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key, ""))
        for key in ("semantic_role", "object_kind", "kind", "slot_type")
    ).lower()


def is_semantic_text(item: dict[str, Any]) -> bool:
    text = role_text(item)
    return any(token in text for token in TEXT_TOKENS)


def is_structured_semantic(item: dict[str, Any]) -> bool:
    text = role_text(item)
    return any(token in text for token in STRUCTURED_TOKENS)


def is_semantic_object(item: dict[str, Any]) -> bool:
    return bool(item.get("content_bearing") or item.get("editable_required") or is_semantic_text(item) or is_structured_semantic(item))


def is_raster_target(target: str | None) -> bool:
    return str(target or "") in RASTER_TARGETS


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)
