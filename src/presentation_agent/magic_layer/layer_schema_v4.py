"""Schema helpers for Magic Layer layer_manifest_v4."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


ALLOWED_LAYER_TYPES = {
    "background_base",
    "decorative_texture",
    "hero_visual_field",
    "image_frame",
    "title_text_region",
    "subtitle_text_region",
    "body_text_region",
    "card_panel",
    "icon_region",
    "chart_region",
    "table_region",
    "matrix_region",
    "process_node",
    "timeline_phase",
    "connector",
    "source_footer_strip",
    "technical_overlay",
    "accent_line",
    "shadow_or_glow",
    "crop_mask_frame",
    "unknown",
}

ALLOWED_EDITABILITY_TARGETS = {
    "ppt_text",
    "ppt_shape",
    "svg_vector",
    "editable_chart",
    "editable_table",
    "replaceable_image_frame",
    "allowed_decorative_raster",
    "reject_or_patch",
    "unknown_pending_review",
}

ALLOWED_SOURCES = {
    "auto_cv",
    "rule_based",
    "manual_declared",
    "inherited_from_reference_contract",
    "unknown",
}

ALLOWED_UNKNOWN_DISPOSITIONS = {
    "not_unknown",
    "blocking_content_bearing_unknown",
    "bounded_decorative_unknown",
    "review_required",
}

REQUIRED_LAYER_FIELDS = {
    "layer_id",
    "reference_id",
    "bbox_px",
    "bbox_norm",
    "polygon_px",
    "polygon_norm",
    "mask_path",
    "crop_path",
    "z_order",
    "layer_type",
    "semantic_role",
    "component_identity_candidate",
    "content_bearing",
    "editability_target",
    "raster_policy",
    "source",
    "confidence",
    "unknown_disposition",
    "dependencies",
    "notes",
}


class LayerValidationError(ValueError):
    """Raised when a layer manifest does not satisfy schema v4."""


def bbox_norm(bbox_px: list[int] | tuple[int, int, int, int], width: int, height: int) -> list[float]:
    x, y, w, h = [int(v) for v in bbox_px]
    if width <= 0 or height <= 0:
        raise LayerValidationError("Image dimensions must be positive.")
    return [
        round(x / width, 6),
        round(y / height, 6),
        round(w / width, 6),
        round(h / height, 6),
    ]


def polygon_norm(polygon_px: list[list[int]] | None, width: int, height: int) -> list[list[float]] | None:
    if not polygon_px:
        return None
    return [[round(x / width, 6), round(y / height, 6)] for x, y in polygon_px]


def bbox_area_ratio(bbox_px: list[int] | tuple[int, int, int, int], width: int, height: int) -> float:
    _x, _y, w, h = [int(v) for v in bbox_px]
    return (w * h) / (width * height) if width and height else 0.0


def is_full_slide_like(bbox_px: list[int] | tuple[int, int, int, int], width: int, height: int, threshold: float = 0.75) -> bool:
    return bbox_area_ratio(bbox_px, width, height) > threshold


def make_layer(
    *,
    layer_id: str,
    reference_id: str,
    bbox_px: list[int] | tuple[int, int, int, int],
    image_width: int,
    image_height: int,
    layer_type: str,
    semantic_role: str,
    source: str,
    confidence: float,
    archetype_hint: str | None = None,
    z_order: int = 0,
    content_bearing: bool = False,
    editability_target: str = "ppt_shape",
    raster_policy: str = "analysis_crop_only",
    component_identity_candidate: dict[str, Any] | None = None,
    polygon_px: list[list[int]] | None = None,
    crop_path: str | None = None,
    mask_path: str | None = None,
    unknown_disposition: str | None = None,
    dependencies: list[str] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    unknown = unknown_disposition
    if unknown is None:
        unknown = "review_required" if layer_type == "unknown" else "not_unknown"
    layer = {
        "layer_id": layer_id,
        "reference_id": reference_id,
        "archetype_hint": archetype_hint or "unknown",
        "bbox_px": [int(v) for v in bbox_px],
        "bbox_norm": bbox_norm(bbox_px, image_width, image_height),
        "polygon_px": deepcopy(polygon_px),
        "polygon_norm": polygon_norm(polygon_px, image_width, image_height),
        "mask_path": mask_path,
        "crop_path": crop_path,
        "z_order": int(z_order),
        "layer_type": layer_type,
        "semantic_role": semantic_role,
        "component_identity_candidate": deepcopy(component_identity_candidate) if component_identity_candidate is not None else _default_component_identity_candidate(layer_type),
        "content_bearing": bool(content_bearing),
        "editability_target": editability_target,
        "raster_policy": raster_policy,
        "source": source,
        "confidence": round(float(confidence), 4),
        "unknown_disposition": unknown,
        "dependencies": list(dependencies or []),
        "notes": notes,
    }
    validate_layer(layer, image_width=image_width, image_height=image_height)
    return layer


def validate_layer(layer: dict[str, Any], *, image_width: int, image_height: int) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_LAYER_FIELDS.difference(layer)
    if missing:
        errors.append(f"missing_fields:{','.join(sorted(missing))}")
    layer_type = layer.get("layer_type")
    if layer_type not in ALLOWED_LAYER_TYPES:
        errors.append(f"invalid_layer_type:{layer_type}")
    target = layer.get("editability_target")
    if target not in ALLOWED_EDITABILITY_TARGETS:
        errors.append(f"invalid_editability_target:{target}")
    source = layer.get("source")
    if source not in ALLOWED_SOURCES:
        errors.append(f"invalid_source:{source}")
    unknown = layer.get("unknown_disposition")
    if unknown not in ALLOWED_UNKNOWN_DISPOSITIONS:
        errors.append(f"invalid_unknown_disposition:{unknown}")
    bbox = layer.get("bbox_px")
    if not isinstance(bbox, list) or len(bbox) != 4:
        errors.append("invalid_bbox_px")
    else:
        x, y, w, h = bbox
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > image_width + 1 or y + h > image_height + 1:
            errors.append("bbox_out_of_bounds")
        if layer.get("crop_path") and is_full_slide_like(bbox, image_width, image_height) and layer_type != "background_base":
            errors.append("full_slide_crop_not_allowed")
    if layer_type == "unknown" and unknown == "not_unknown":
        errors.append("unknown_layer_requires_disposition")
    if layer_type == "unknown" and layer.get("content_bearing") and unknown != "blocking_content_bearing_unknown":
        errors.append("content_bearing_unknown_must_block")
    if not isinstance(layer.get("component_identity_candidate"), dict):
        errors.append("invalid_component_identity_candidate")
    if layer.get("confidence") is None or not 0 <= float(layer["confidence"]) <= 1:
        errors.append("confidence_out_of_range")
    if errors:
        raise LayerValidationError(";".join(errors))
    return []


def _default_component_identity_candidate(layer_type: str) -> dict[str, Any]:
    mapping = {
        "chart_region": ["chart", "dashboard_chart", "editable_shape_chart"],
        "table_region": ["table_grid", "evidence_table", "editable_shape_grid_table"],
        "matrix_region": ["comparison_matrix", "editable_shape_grid_table"],
        "process_node": ["process_flow", "process_step_node"],
        "timeline_phase": ["timeline_roadmap", "timeline_phase_band"],
        "connector": ["connector", "process_flow", "timeline_roadmap"],
        "card_panel": ["card_panel", "evidence_card_grid"],
        "icon_region": ["icon", "svg_vector_icon"],
        "hero_visual_field": ["diagonal_image_mask", "replaceable_image_frame"],
        "image_frame": ["photo_caption_grid", "replaceable_image_frame"],
        "source_footer_strip": ["source_footer_strip"],
        "technical_overlay": ["technical_overlay"],
    }
    candidates = mapping.get(layer_type, [layer_type])
    return {
        "primary": candidates[0],
        "candidates": candidates,
        "confidence": 0.5 if layer_type != "unknown" else 0.0,
        "promotion_stage": "D03_D04_candidate" if layer_type in mapping else "review_required",
        "notes": "Initial D01 geometry/type candidate; not final semantic promotion.",
    }


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    metadata = manifest.get("reference_metadata") or {}
    width = metadata.get("width")
    height = metadata.get("height")
    if not width or not height:
        errors.append("missing_reference_dimensions")
        return errors
    for layer in manifest.get("layers", []):
        try:
            validate_layer(layer, image_width=int(width), image_height=int(height))
        except LayerValidationError as exc:
            errors.append(f"{layer.get('layer_id', '<unknown>')}:{exc}")
    return errors
