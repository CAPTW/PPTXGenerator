"""Record-level validators for the Photoshop-inspired Magic Layer+ protocol."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.ps_layer_protocol import bbox_area, bbox_inside_slide, normalize_bbox, point_inside_slide


REQUIRED_LAYER_FIELDS = {
    "layer_id",
    "layer_name",
    "group_id",
    "layer_kind",
    "semantic_role",
    "content_bearing",
    "bbox_norm",
    "z_order",
    "editability_target",
    "pptx_target",
    "raster_policy",
    "unknown_disposition",
    "confidence",
}

SEMANTIC_LAYER_KINDS = {"text", "semantic_icon", "table", "chart", "card", "panel"}
RASTER_TARGETS = {"bounded_nonsemantic_raster", "bounded_nonsemantic_texture", "vector_texture"}
PPTX_TARGETS_BY_KIND = {
    "text": {"ppt_text_box"},
    "shape": {"ppt_shape", "ppt_group"},
    "card": {"ppt_shape", "ppt_group"},
    "panel": {"ppt_shape", "ppt_group"},
    "semantic_icon": {"svg_vector", "native_vector", "ppt_freeform_vector", "native_freeform"},
    "table": {"native_table", "editable_shape_grid_table"},
    "chart": {"native_chart", "editable_shape_chart"},
    "smart_object_like_image": {"replaceable_image_frame"},
    "decorative_texture": {"bounded_nonsemantic_raster", "bounded_nonsemantic_texture", "vector_texture", "svg_vector"},
    "background_base": {"ppt_shape_background"},
    "connector": {"ppt_connector", "ppt_shape", "ppt_group"},
    "technical_overlay": {"ppt_shape", "ppt_group", "svg_vector"},
    "unknown": {"reject"},
}


def validate_layer_records(protocol: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for layer in protocol.get("layers", []):
        layer_id = layer.get("layer_id", "<missing>")
        missing = sorted(REQUIRED_LAYER_FIELDS - set(layer))
        for field in missing:
            errors.append(_issue("missing_required_layer_field", layer_id, field=field))
        if "bbox_norm" in layer:
            _validate_bbox(layer, errors)
        if layer.get("layer_kind") == "unknown" and layer.get("content_bearing") is True:
            errors.append(_issue("unknown_content_bearing_layer", layer_id))
        if layer.get("content_bearing") is True and not layer.get("semantic_role"):
            errors.append(_issue("missing_semantic_role_for_content_bearing_layer", layer_id))
        _validate_target_mapping(layer, errors, warnings)
        _validate_raster_policy(layer, errors)
    return _report("ps_layer_record_validation_report", errors, warnings, layer_count=len(protocol.get("layers", [])))


def validate_masks(protocol: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    layers = {layer.get("layer_id"): layer for layer in protocol.get("layers", [])}
    for mask in protocol.get("masks", []):
        mask_id = mask.get("mask_id", "<missing>")
        for field in ("mask_id", "target_layer_id", "mask_type", "bbox_norm", "pptx_rendering_strategy", "fallback_policy"):
            if field not in mask or mask.get(field) in (None, ""):
                errors.append(_issue("missing_required_mask_field", mask_id, field=field))
        if "bbox_norm" in mask and not bbox_inside_slide(mask["bbox_norm"]):
            errors.append(_issue("mask_bbox_outside_bounds", mask_id))
        points = mask.get("polygon_points_norm") or []
        if not points and not mask.get("alpha_source_ref") and mask.get("mask_type") not in {"none", None}:
            errors.append(_issue("mask_missing_polygon_or_alpha_source", mask_id))
        for point in points:
            if not point_inside_slide(point):
                errors.append(_issue("mask_point_outside_bounds", mask_id, point=point))
        target = layers.get(mask.get("target_layer_id"))
        if target is None:
            errors.append(_issue("mask_target_layer_missing", mask_id, target_layer_id=mask.get("target_layer_id")))
            continue
        if mask.get("pptx_rendering_strategy") == "bounded_nonsemantic_raster_fallback" and _is_semantic_layer(target):
            errors.append(_issue("semantic_layer_uses_bounded_raster_fallback", mask_id, target_layer_id=target.get("layer_id")))
        if target.get("layer_kind") == "smart_object_like_image" and _target_kind(target) != "replaceable_image_frame":
            errors.append(_issue("smart_object_mask_without_replaceable_image_frame", mask_id, target_layer_id=target.get("layer_id")))
    return _report("mask_rendering_strategy_validation_report", errors, warnings, mask_count=len(protocol.get("masks", [])))


def validate_smart_objects(protocol: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    count = 0
    for layer in protocol.get("layers", []):
        if layer.get("layer_kind") != "smart_object_like_image":
            continue
        count += 1
        layer_id = layer.get("layer_id", "<missing>")
        try:
            bbox = normalize_bbox(layer.get("bbox_norm"))
            if bbox_area(bbox) >= 0.95 or (bbox["x"] <= 0.001 and bbox["y"] <= 0.001 and bbox["w"] >= 0.999 and bbox["h"] >= 0.999):
                errors.append(_issue("smart_object_full_slide", layer_id))
        except (KeyError, TypeError, ValueError):
            errors.append(_issue("smart_object_invalid_bbox", layer_id))
        role = str(layer.get("semantic_role", ""))
        if layer.get("semantic_content_allowed") is True:
            errors.append(_issue("smart_object_semantic_content_allowed", layer_id))
        if any(token in role for token in ("text", "chart", "table", "icon", "card", "footer")) and role != "hero_visual_field":
            errors.append(_issue("smart_object_contains_semantic_role", layer_id, semantic_role=role))
        if not layer.get("asset_ref"):
            errors.append(_issue("smart_object_missing_asset_ref", layer_id))
        if _target_kind(layer) != "replaceable_image_frame" or layer.get("editability_target") != "replaceable_image_frame":
            errors.append(_issue("smart_object_not_replaceable", layer_id))
    return _report("smart_object_policy_validation_report", errors, warnings, smart_object_count=count)


def validate_layer_cleanup(protocol: dict[str, Any], cleanup_rules: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for layer in protocol.get("layers", []):
        layer_id = layer.get("layer_id", "<missing>")
        name = str(layer.get("layer_name", ""))
        role = str(layer.get("semantic_role", ""))
        if not name:
            errors.append(_issue("layer_name_missing", layer_id))
            continue
        prefix = name.split(".")[0]
        allowed = _role_name_prefixes(role)
        if allowed and prefix not in allowed:
            warnings.append(_issue("layer_name_prefix_mismatch", layer_id, layer_name=name, semantic_role=role, allowed_prefixes=sorted(allowed)))
        if layer.get("content_bearing") is True and layer.get("unknown_disposition") in {"requires_manual_review", "reject_content_bearing_unknown"}:
            errors.append(_issue("cleanup_blocks_content_bearing_unknown", layer_id))
    return _report("layer_cleanup_gate_report", errors, warnings, layer_count=len(protocol.get("layers", [])))


def _validate_bbox(layer: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    layer_id = layer.get("layer_id", "<missing>")
    try:
        if not bbox_inside_slide(layer["bbox_norm"]):
            errors.append(_issue("bbox_norm_outside_slide_bounds", layer_id))
        if bbox_area(layer["bbox_norm"]) <= 0:
            errors.append(_issue("bbox_zero_or_negative_area", layer_id))
    except (KeyError, TypeError, ValueError):
        errors.append(_issue("bbox_norm_invalid", layer_id))


def _validate_target_mapping(layer: dict[str, Any], errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    layer_id = layer.get("layer_id", "<missing>")
    kind = layer.get("layer_kind")
    target = _target_kind(layer)
    allowed = PPTX_TARGETS_BY_KIND.get(kind)
    if allowed and target not in allowed:
        errors.append(_issue("pptx_target_conflicts_with_layer_kind", layer_id, layer_kind=kind, target_kind=target, allowed=sorted(allowed)))
    if layer.get("semantic_role") == "background_base":
        if target != "ppt_shape_background":
            errors.append(_issue("background_base_target_not_ppt_shape_background", layer_id, target_kind=target))
        if bbox_area(layer.get("bbox_norm", [0, 0, 0, 0])) >= 0.95 and target in {"replaceable_image_frame", "bounded_nonsemantic_raster", "bounded_nonsemantic_texture"}:
            errors.append(_issue("background_base_full_slide_image", layer_id, target_kind=target))
    if kind in {"semantic_icon", "table", "chart"} and target in RASTER_TARGETS:
        errors.append(_issue(f"{kind}_maps_to_raster", layer_id, target_kind=target))
    if any(token in str(layer.get("semantic_role", "")) for token in ("footer", "source")) and target in RASTER_TARGETS:
        errors.append(_issue("footer_or_source_maps_to_raster", layer_id, target_kind=target))
    if kind in {"card", "panel"} and target in RASTER_TARGETS:
        errors.append(_issue("card_or_panel_maps_to_raster", layer_id, target_kind=target))


def _validate_raster_policy(layer: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    layer_id = layer.get("layer_id", "<missing>")
    policy = layer.get("raster_policy") or {}
    final_use = policy.get("final_use")
    target = _target_kind(layer)
    if _is_semantic_layer(layer) and (final_use == "bounded_nonsemantic_raster" or target in RASTER_TARGETS):
        errors.append(_issue("semantic_layer_maps_to_raster", layer_id, final_use=final_use, target_kind=target))
    if final_use == "bounded_nonsemantic_raster" and not policy.get("bounded"):
        errors.append(_issue("nonsemantic_raster_unbounded", layer_id))
    if bbox_area(layer.get("bbox_norm", [0, 0, 0, 0])) >= 0.95 and final_use in {"replaceable_image_frame", "bounded_nonsemantic_raster"}:
        errors.append(_issue("full_slide_raster_or_image_frame", layer_id, final_use=final_use))


def _is_semantic_layer(layer: dict[str, Any]) -> bool:
    role = str(layer.get("semantic_role", ""))
    role_tokens = set(role.split("_"))
    return layer.get("content_bearing") is True or layer.get("layer_kind") in SEMANTIC_LAYER_KINDS or any(
        token in role_tokens for token in ("text", "icon", "chart", "table", "card", "footer", "source")
    )


def _target_kind(layer: dict[str, Any]) -> str | None:
    target = layer.get("pptx_target") or {}
    return target.get("target_kind")


def _role_name_prefixes(role: str) -> set[str]:
    if not role:
        return set()
    if role.startswith("source_footer") or role.startswith("footer"):
        return {"footer", "source"}
    if role.startswith("hero"):
        return {"hero", "image"}
    if role.startswith("semantic_icon") or role.startswith("icon"):
        return {"icon"}
    return {role.split("_")[0]}


def _issue(code: str, layer_id: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, "layer_id": layer_id, **extra}


def _report(schema_name: str, errors: list[dict[str, Any]], warnings: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "schema_name": schema_name,
        "status": "passed" if not errors else "failed",
        "failure_codes": sorted({error["code"] for error in errors}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
        "errors": errors,
        "warnings": warnings,
        **extra,
        "canva_parity_claimed": False,
    }
