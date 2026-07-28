from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.presentation_agent.magic_layer.schemas.common import bbox_valid


SOURCE_IMAGE_KINDS = {"reference", "render", "contact_sheet", "comparison"}
COORDINATE_SPACES = {"pixel", "normalized"}
OVERLAY_CATEGORIES = {
    "object_bbox",
    "layer_bbox",
    "slot_bbox",
    "text_region",
    "image_field",
    "chart_region",
    "table_region",
    "semantic_raster_violation",
    "unknown_content_bearing",
    "text_overflow_risk",
    "residual_raster_text_risk",
    "native_plate_visual_risk",
    "full_slide_raster_risk",
    "patch_target",
}
SEVERITIES = {"info", "warning", "high", "fatal"}
DRAW_STYLES = {"outline", "filled_translucent", "label_only", "crosshatch"}


def validate_overlay_document(document: dict[str, Any]) -> dict[str, Any]:
    doc = deepcopy(document)
    failures: list[str] = []
    warnings: list[str] = []
    if doc.get("schema", "overlay_document.v1") != "overlay_document.v1":
        failures.append("schema must be overlay_document.v1")
    if not doc.get("overlay_id"):
        failures.append("overlay_id is required")
    if doc.get("source_image_kind", "render") not in SOURCE_IMAGE_KINDS:
        failures.append("source_image_kind is invalid")
    if doc.get("coordinate_space", "normalized") not in COORDINATE_SPACES:
        failures.append("coordinate_space is invalid")
    overlays = doc.get("overlays", [])
    if not isinstance(overlays, list):
        failures.append("overlays must be a list")
        overlays = []
    normalized_items: list[dict[str, Any]] = []
    fatal_count = 0
    for index, item in enumerate(overlays):
        if not isinstance(item, dict):
            failures.append(f"overlay item {index} must be object")
            continue
        normalized = deepcopy(item)
        normalized.setdefault("overlay_item_id", f"overlay_{index + 1}")
        normalized.setdefault("label", normalized.get("object_id") or normalized.get("layer_id") or normalized["overlay_item_id"])
        normalized.setdefault("category", "object_bbox")
        normalized.setdefault("severity", "info")
        normalized.setdefault("draw_style", "outline")
        normalized.setdefault("message", "")
        normalized.setdefault("evidence_paths", [])
        if normalized["category"] not in OVERLAY_CATEGORIES:
            failures.append(f"{normalized['overlay_item_id']}: category is invalid")
        if normalized["severity"] not in SEVERITIES:
            failures.append(f"{normalized['overlay_item_id']}: severity is invalid")
        if normalized["draw_style"] not in DRAW_STYLES:
            failures.append(f"{normalized['overlay_item_id']}: draw_style is invalid")
        if "bbox_norm" in normalized and normalized["bbox_norm"] is not None:
            if not bbox_valid(normalized["bbox_norm"]):
                failures.append(f"{normalized['overlay_item_id']}: bbox_norm invalid")
        elif "bbox_px" in normalized and normalized["bbox_px"] is not None:
            if not _bbox_px_valid(normalized["bbox_px"]):
                failures.append(f"{normalized['overlay_item_id']}: bbox_px invalid")
        else:
            warnings.append(f"{normalized['overlay_item_id']}: bbox missing; overlay cannot be drawn")
        if normalized["severity"] == "fatal":
            fatal_count += 1
        normalized_items.append(normalized)
    return {
        "schema": "overlay_document_validation.v1",
        "pass": not failures,
        "failures": failures,
        "warnings": warnings,
        "overlays": normalized_items,
        "fatal_issue_count": fatal_count,
    }


def _bbox_px_valid(bbox: Any) -> bool:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return False
    if not all(isinstance(value, (int, float)) for value in bbox):
        return False
    _x, _y, width, height = [float(value) for value in bbox]
    return width > 0 and height > 0


def bbox_norm_to_px(bbox: list[float], width: int, height: int) -> list[int]:
    x, y, w, h = [float(value) for value in bbox]
    return [round(x * width), round(y * height), round(w * width), round(h * height)]
