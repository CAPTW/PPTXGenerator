"""Map D01/D02 layers into PPT primitive families."""

from __future__ import annotations

from typing import Any

from .primitive_family_taxonomy import family_spec


def map_primitive_regions(manifest: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    reference_id = manifest.get("reference_id") or "reference"
    mappings = []
    unresolved = []
    for layer in manifest.get("layers") or []:
        mapping = _primitive_mapping_for_layer(layer, reference_id, taxonomy)
        mappings.append(mapping)
        if mapping["primitive_family"] == "unknown_primitive" or mapping.get("unresolved_reason"):
            unresolved.append(mapping)
    return {
        "schema_name": "ppt_primitive_mapping",
        "reference_id": reference_id,
        "primitive_mappings": mappings,
        "unresolved_primitives": unresolved,
        "unresolved_primitive_count": len(unresolved),
        "source_footer_mapping_exists": any(item["primitive_family"] == "source_footer_strip" for item in mappings),
    }


def validate_primitive_mapping(mapping: dict[str, Any]) -> list[str]:
    required = {
        "primitive_id",
        "source_layer_ids",
        "bbox_px",
        "bbox_norm",
        "primitive_family",
        "semantic_role",
        "target_ppt_object_type",
        "editability_target",
        "raster_policy",
        "z_order",
        "dependencies",
        "confidence",
        "handoff_stage",
        "unresolved_reason",
    }
    errors = []
    missing = required.difference(mapping)
    if missing:
        errors.append(f"missing_fields:{','.join(sorted(missing))}")
    if mapping.get("primitive_family") in {"chart_region", "table_region", "matrix_region", "comparison_matrix_grid"}:
        if mapping.get("handoff_stage") != "D04":
            errors.append("chart_table_like_primitive_must_handoff_D04")
        if "decorative" in str(mapping.get("raster_policy")):
            errors.append("chart_table_like_primitive_cannot_be_decorative")
    if mapping.get("primitive_family") == "source_footer_strip" and "decorative" in str(mapping.get("raster_policy")):
        errors.append("source_footer_primitive_cannot_be_decorative")
    return errors


def _primitive_mapping_for_layer(layer: dict[str, Any], reference_id: str, taxonomy: dict[str, Any]) -> dict[str, Any]:
    family = _family_for_layer(layer, reference_id)
    spec = family_spec(taxonomy, family) or family_spec(taxonomy, "unknown_primitive") or {}
    target = spec.get("target_ppt_implementation") or "reject_or_patch"
    handoff = _handoff_stage(family, reference_id, layer)
    unresolved_reason = ""
    if family == "unknown_primitive":
        unresolved_reason = "unknown_primitive_requires_review"
    elif layer.get("layer_type") == "unknown" and layer.get("content_bearing"):
        unresolved_reason = "content_bearing_unknown_requires_review"
    return {
        "primitive_id": f"{reference_id}_primitive_{layer['layer_id']}",
        "source_layer_ids": [layer["layer_id"]],
        "bbox_px": layer["bbox_px"],
        "bbox_norm": layer["bbox_norm"],
        "primitive_family": family,
        "semantic_role": layer.get("semantic_role"),
        "target_ppt_object_type": target,
        "editability_target": spec.get("allowed_editability_target") or layer.get("editability_target"),
        "raster_policy": spec.get("raster_policy") or layer.get("raster_policy"),
        "z_order": layer.get("z_order"),
        "dependencies": layer.get("dependencies") or [],
        "confidence": _confidence(layer, family, reference_id),
        "handoff_stage": handoff,
        "unresolved_reason": unresolved_reason,
    }


def _family_for_layer(layer: dict[str, Any], reference_id: str) -> str:
    layer_type = str(layer.get("layer_type") or "")
    semantic = str(layer.get("semantic_role") or "").lower()
    if layer_type == "source_footer_strip" or "source_footer" in semantic:
        return "source_footer_strip"
    if layer_type == "title_text_region":
        return "title_text_region"
    if layer_type in {"subtitle_text_region", "body_text_region"}:
        return "body_text_region"
    if layer_type == "background_base":
        return "background_base"
    if layer_type == "card_panel":
        return "card_panel"
    if layer_type == "connector":
        return "connector_line"
    if layer_type == "accent_line":
        return "accent_line"
    if layer_type == "technical_overlay":
        return "technical_overlay"
    if layer_type == "hero_visual_field":
        return "hero_visual_field"
    if layer_type == "image_frame":
        return "replaceable_image_frame"
    if layer_type == "process_node":
        return "process_node"
    if layer_type == "timeline_phase":
        return "timeline_phase"
    if layer_type == "matrix_region":
        return "matrix_region"
    if layer_type == "table_region":
        return "table_region"
    if layer_type == "chart_region":
        return "chart_region"
    if layer_type == "icon_region":
        if reference_id == "data_dashboard":
            return "chart_frame"
        if reference_id == "table_heavy":
            return "table_region"
        return "callout_panel"
    if layer_type == "unknown":
        return "unknown_primitive"
    return "unknown_primitive"


def _handoff_stage(family: str, reference_id: str, layer: dict[str, Any]) -> str:
    if family in {"chart_region", "table_region", "matrix_region", "comparison_matrix_grid", "chart_frame", "legend_group", "axis_label_group"}:
        return "D04"
    if reference_id in {"data_dashboard", "table_heavy", "canva_benchmark"} and layer.get("layer_type") in {"icon_region", "connector", "accent_line"}:
        return "D04"
    if family == "unknown_primitive":
        return "D05"
    return "D05"


def _confidence(layer: dict[str, Any], family: str, reference_id: str) -> float:
    base = float(layer.get("confidence") or 0.0)
    if family in {"source_footer_strip", "title_text_region", "body_text_region"}:
        return round(max(base, 0.72), 4)
    if family in {"chart_frame", "table_region"} and reference_id in {"data_dashboard", "table_heavy"}:
        return round(max(base, 0.58), 4)
    if family == "unknown_primitive":
        return min(base, 0.25)
    return round(max(base, 0.55), 4)

