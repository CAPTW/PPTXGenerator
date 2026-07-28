"""Resolve major visual regions for D05.1 render fidelity patches."""

from __future__ import annotations

from pathlib import Path
from typing import Any


MAJOR_REGION_TYPES = {
    "background_base",
    "hero_visual_field",
    "image_frame",
    "title_cluster",
    "card_panel_group",
    "right_side_rail",
    "bottom_footer_source_strip",
    "chart_frame",
    "table_frame",
    "primary_content_grid",
    "technical_overlay_group",
}


def major_region_preservation_policy() -> dict[str, Any]:
    return {
        "schema_name": "major_region_preservation_policy_v1",
        "major_region_types": sorted(MAJOR_REGION_TYPES),
        "rules": {
            "full_slide_reference_background_allowed": False,
            "screenshot_slide_allowed": False,
            "major_visual_fields_required": True,
            "major_region_absence_blocks_D06": True,
            "scoped_visual_crops_allowed_for_nonsemantic_visual_fields": True,
            "semantic_text_icon_chart_table_raster_forbidden": True,
            "fallback_skeletons_must_be_recorded": True,
        },
    }


def archetype_render_fidelity_thresholds() -> dict[str, Any]:
    return {
        "schema_name": "archetype_render_fidelity_thresholds_v1",
        "minimum_product_thresholds": {
            "recognizable_archetype_identity": True,
            "major_region_coverage": "acceptable",
            "composition_alignment": "acceptable",
            "source_footer_region_visible_where_applicable": True,
            "visual_density_not_sparse_debug_like": True,
            "no_full_slide_raster_cheat": True,
            "no_semantic_raster_cheat": True,
            "chart_table_skeleton_visually_aligned_where_applicable": True,
        },
        "metric_policy": "SSIM/MAE are supporting evidence; final judgment uses major-region and product-fidelity gates.",
    }


def resolve_major_regions(reference_id: str, manifest: dict[str, Any], reference_image_path: Path) -> dict[str, Any]:
    """Return major regions from layer evidence plus recorded skeleton fallbacks."""

    layers = manifest.get("layers") or []
    evidence_regions = _regions_from_layers(reference_id, layers)
    fallback_regions = _fallback_regions(reference_id, reference_image_path)
    by_id = {item["region_id"]: item for item in fallback_regions}
    for item in evidence_regions:
        by_id.setdefault(item["region_id"], item)
    regions = list(by_id.values())
    missing = _missing_required(reference_id, regions)
    return {
        "schema_name": "major_region_resolution",
        "reference_id": reference_id,
        "reference_image_path": reference_image_path.as_posix(),
        "status": "passed" if not missing else "missing_major_regions",
        "major_regions": regions,
        "missing_required_region_types": missing,
        "major_region_count": len(regions),
        "recorded_fallback_count": len([item for item in regions if item.get("source") == "archetype_composition_skeleton"]),
    }


def major_region_coverage_report(reference_id: str, resolution: dict[str, Any], candidate_spec: dict[str, Any]) -> dict[str, Any]:
    required = set(_required_types(reference_id))
    covered = {obj.get("major_region_type") for obj in candidate_spec.get("objects") or [] if obj.get("major_region_type")}
    missing = sorted(required.difference(covered))
    sparse = len([obj for obj in candidate_spec.get("objects") or [] if obj.get("object_type") != "ppt_text"]) < 8
    return {
        "schema_name": "major_region_coverage_report",
        "reference_id": reference_id,
        "status": "passed" if not missing and not sparse else "failed",
        "required_region_types": sorted(required),
        "covered_region_types": sorted(item for item in covered if item),
        "missing_region_types": missing,
        "sparse_debug_like": sparse,
        "major_region_count": resolution.get("major_region_count", 0),
    }


def scoped_raster_visual_field_policy() -> dict[str, Any]:
    return {
        "schema_name": "scoped_raster_visual_field_policy_v1",
        "allowed": [
            "hero/photo field crop",
            "abstract visual field crop",
            "decorative texture crop",
            "non-semantic technical texture crop",
            "bounded benchmark visual segment for comparison only",
        ],
        "forbidden": [
            "full-slide raster",
            "screenshot slide",
            "semantic text raster",
            "semantic icon raster",
            "semantic chart/table raster",
            "source/footer text raster",
        ],
        "max_area_ratio": 0.7,
        "semantic_raster_final_use_allowed": False,
    }


def validate_scoped_visual_field(obj: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    bbox = obj.get("bbox_norm") or []
    if len(bbox) != 4:
        errors.append("invalid_bbox_norm")
        return errors
    area = float(bbox[2]) * float(bbox[3])
    if area >= 0.75:
        errors.append("scoped_visual_field_cannot_be_full_slide")
    if obj.get("semantic_component") in {"text", "icon", "chart", "table", "matrix", "source_footer"}:
        errors.append("semantic_component_cannot_be_scoped_raster")
    if obj.get("final_use") != "allowed_scoped_visual_field_raster":
        errors.append("scoped_visual_field_requires_allowed_raster_final_use")
    return errors


def _regions_from_layers(reference_id: str, layers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    for layer in layers:
        layer_type = layer.get("layer_type")
        family = layer.get("primitive_family")
        area = _area(layer.get("bbox_norm"))
        if layer_type == "source_footer_strip" and area > 0.025:
            regions.append(_shape_region(reference_id, "bottom_footer_source_strip", layer, "#0F172A", "#38BDF8"))
        elif layer_type == "card_panel" and area > 0.035:
            regions.append(_shape_region(reference_id, "card_panel_group", layer, "#F8FAFC", "#D1D5DB"))
        elif family in {"chart_region", "chart_frame"} and area > 0.08:
            regions.append(_shape_region(reference_id, "chart_frame", layer, "#F8FAFC", "#38BDF8"))
        elif family in {"table_region", "matrix_region"} and area > 0.08:
            regions.append(_shape_region(reference_id, "table_frame", layer, "#F8FAFC", "#38BDF8"))
        elif layer_type in {"hero_visual_field", "image_frame"} and area <= 0.7:
            regions.append(_scoped_crop_region(reference_id, "hero_visual_field", layer))
    return regions


def _fallback_regions(reference_id: str, reference_image_path: Path) -> list[dict[str, Any]]:
    skeletons: dict[str, list[dict[str, Any]]] = {
        "canva_benchmark": [
            _crop("photo_visual_field", "hero_visual_field", [0.0, 0.18, 0.47, 0.55], reference_image_path, "bounded benchmark photo/industrial visual segment"),
            _shape("checklist_panel", "primary_content_grid", [0.50, 0.09, 0.43, 0.60], "#0B2130", "#18A7B5"),
            _shape("checklist_rows", "card_panel_group", [0.54, 0.17, 0.34, 0.45], "#123444", "#18A7B5"),
            _shape("checklist_row_01", "card_panel_group", [0.56, 0.18, 0.31, 0.065], "#173A49", "#18A7B5"),
            _shape("checklist_row_02", "card_panel_group", [0.56, 0.265, 0.31, 0.065], "#173A49", "#18A7B5"),
            _shape("checklist_row_03", "card_panel_group", [0.56, 0.35, 0.31, 0.065], "#173A49", "#18A7B5"),
            _shape("checklist_row_04", "card_panel_group", [0.56, 0.435, 0.31, 0.065], "#173A49", "#18A7B5"),
            _shape("checklist_row_05", "card_panel_group", [0.56, 0.52, 0.31, 0.065], "#173A49", "#18A7B5"),
            _shape("bottom_safety_banner", "bottom_footer_source_strip", [0.0, 0.74, 0.97, 0.19], "#111827", "#F59E0B"),
            _shape("bottom_banner_item_01", "bottom_footer_source_strip", [0.05, 0.80, 0.13, 0.055], "#18232F", "#F59E0B"),
            _shape("bottom_banner_item_02", "bottom_footer_source_strip", [0.23, 0.80, 0.13, 0.055], "#18232F", "#F59E0B"),
            _shape("bottom_banner_item_03", "bottom_footer_source_strip", [0.41, 0.80, 0.13, 0.055], "#18232F", "#F59E0B"),
            _shape("bottom_banner_item_04", "bottom_footer_source_strip", [0.59, 0.80, 0.13, 0.055], "#18232F", "#F59E0B"),
            _shape("bottom_banner_item_05", "bottom_footer_source_strip", [0.77, 0.80, 0.13, 0.055], "#18232F", "#F59E0B"),
        ],
        "cover_hero": [
            _crop("right_hero_visual_field", "hero_visual_field", [0.46, 0.02, 0.52, 0.84], reference_image_path, "bounded abstract hero visual field"),
            _shape("left_title_cluster", "title_cluster", [0.03, 0.20, 0.34, 0.42], "#0B1528", "#38BDF8"),
            _shape("diagonal_rail", "technical_overlay_group", [0.42, 0.02, 0.035, 0.84], "#0E7490", "#F59E0B"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.0, 0.88, 1.0, 0.08], "#1F2937", "#38BDF8"),
        ],
        "standard_content": [
            _shape("left_card_grid", "card_panel_group", [0.05, 0.29, 0.44, 0.55], "#F8FAFC", "#CBD5E1"),
            _shape("center_content_panel", "primary_content_grid", [0.50, 0.29, 0.30, 0.55], "#F8FAFC", "#CBD5E1"),
            _shape("right_insight_rail", "right_side_rail", [0.81, 0.12, 0.16, 0.72], "#1F2937", "#F59E0B"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.02, 0.88, 0.96, 0.08], "#1F2937", "#38BDF8"),
        ],
        "data_dashboard": [
            _shape("dashboard_shell", "primary_content_grid", [0.02, 0.05, 0.96, 0.86], "#071A2B", "#38BDF8"),
            _shape("chart_panel", "chart_frame", [0.04, 0.30, 0.58, 0.41], "#F8FAFC", "#CBD5E1"),
            _shape("insight_panel", "right_side_rail", [0.65, 0.30, 0.30, 0.41], "#F8FAFC", "#CBD5E1"),
            _shape("bottom_source_strip", "bottom_footer_source_strip", [0.02, 0.82, 0.96, 0.09], "#1F2937", "#38BDF8"),
        ],
        "table_heavy": [
            _shape("table_header_band", "title_cluster", [0.04, 0.05, 0.92, 0.10], "#071A2B", "#F59E0B"),
            _shape("table_frame", "table_frame", [0.04, 0.18, 0.91, 0.54], "#F8FAFC", "#CBD5E1"),
            _shape("metric_strip", "primary_content_grid", [0.05, 0.74, 0.90, 0.13], "#F8FAFC", "#F59E0B"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.02, 0.90, 0.96, 0.07], "#0F172A", "#38BDF8"),
        ],
        "section_divider": [
            _crop("chapter_visual_field", "hero_visual_field", [0.00, 0.00, 0.42, 0.86], reference_image_path, "bounded section visual field"),
            _shape("section_title_cluster", "title_cluster", [0.48, 0.25, 0.42, 0.34], "#0B1528", "#F59E0B"),
            _shape("chapter_marker", "technical_overlay_group", [0.48, 0.14, 0.18, 0.08], "#0E7490", "#F59E0B"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.03, 0.88, 0.94, 0.07], "#111827", "#38BDF8"),
        ],
        "visual_toc": [
            _shape("toc_title_cluster", "title_cluster", [0.05, 0.07, 0.48, 0.14], "#0B1528", "#38BDF8"),
            _shape("toc_module_grid", "primary_content_grid", [0.05, 0.25, 0.90, 0.52], "#F8FAFC", "#CBD5E1"),
            _shape("active_path_highlight", "card_panel_group", [0.08, 0.33, 0.84, 0.12], "#DBEAFE", "#38BDF8"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.03, 0.88, 0.94, 0.07], "#111827", "#38BDF8"),
        ],
        "evidence_overview": [
            _shape("evidence_card_grid", "card_panel_group", [0.05, 0.22, 0.63, 0.58], "#F8FAFC", "#CBD5E1"),
            _shape("confidence_rail", "right_side_rail", [0.72, 0.18, 0.23, 0.62], "#0F172A", "#F59E0B"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.03, 0.88, 0.94, 0.07], "#111827", "#38BDF8"),
        ],
        "card_grid": [
            _shape("primary_card_grid", "card_panel_group", [0.05, 0.23, 0.90, 0.58], "#F8FAFC", "#CBD5E1"),
            _shape("grid_header_cluster", "title_cluster", [0.05, 0.07, 0.58, 0.13], "#0B1528", "#38BDF8"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.03, 0.88, 0.94, 0.07], "#111827", "#38BDF8"),
        ],
        "methodology_framework": [
            _shape("framework_stack", "primary_content_grid", [0.07, 0.20, 0.84, 0.52], "#F8FAFC", "#CBD5E1"),
            _shape("framework_layer_cards", "card_panel_group", [0.10, 0.25, 0.58, 0.42], "#EFF6FF", "#38BDF8"),
            _shape("framework_node_01", "card_panel_group", [0.12, 0.28, 0.52, 0.075], "#FFFFFF", "#CBD5E1"),
            _shape("framework_node_02", "card_panel_group", [0.12, 0.39, 0.52, 0.075], "#FFFFFF", "#CBD5E1"),
            _shape("framework_node_03", "card_panel_group", [0.12, 0.50, 0.52, 0.075], "#FFFFFF", "#CBD5E1"),
            _shape("framework_node_04", "card_panel_group", [0.12, 0.61, 0.52, 0.075], "#FFFFFF", "#CBD5E1"),
            _shape("method_side_rail", "right_side_rail", [0.75, 0.16, 0.18, 0.62], "#0F172A", "#F59E0B"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.03, 0.88, 0.94, 0.07], "#111827", "#38BDF8"),
        ],
        "process_flow": [
            _shape("process_lane", "primary_content_grid", [0.05, 0.32, 0.90, 0.26], "#F8FAFC", "#CBD5E1"),
            _shape("process_node_group", "card_panel_group", [0.08, 0.28, 0.84, 0.34], "#EFF6FF", "#38BDF8"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.03, 0.88, 0.94, 0.07], "#111827", "#38BDF8"),
        ],
        "comparison_matrix": [
            _shape("matrix_frame", "table_frame", [0.05, 0.20, 0.90, 0.58], "#F8FAFC", "#CBD5E1"),
            _shape("criteria_header", "title_cluster", [0.05, 0.07, 0.58, 0.13], "#0B1528", "#F59E0B"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.03, 0.88, 0.94, 0.07], "#111827", "#38BDF8"),
        ],
        "timeline_roadmap": [
            _shape("timeline_track", "primary_content_grid", [0.06, 0.37, 0.88, 0.20], "#F8FAFC", "#CBD5E1"),
            _shape("phase_card_group", "card_panel_group", [0.08, 0.24, 0.84, 0.46], "#EFF6FF", "#38BDF8"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.03, 0.88, 0.94, 0.07], "#111827", "#38BDF8"),
        ],
        "decision_record": [
            _shape("decision_panel", "card_panel_group", [0.05, 0.19, 0.43, 0.58], "#F8FAFC", "#CBD5E1"),
            _shape("evidence_status_rail", "right_side_rail", [0.52, 0.19, 0.43, 0.58], "#0F172A", "#F59E0B"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.03, 0.88, 0.94, 0.07], "#111827", "#38BDF8"),
        ],
        "risk_register": [
            _shape("risk_register_grid", "table_frame", [0.04, 0.18, 0.92, 0.60], "#F8FAFC", "#CBD5E1"),
            _shape("risk_row_01", "primary_content_grid", [0.06, 0.25, 0.88, 0.07], "#FFFFFF", "#CBD5E1"),
            _shape("risk_row_02", "primary_content_grid", [0.06, 0.34, 0.88, 0.07], "#EFF6FF", "#CBD5E1"),
            _shape("risk_row_03", "primary_content_grid", [0.06, 0.43, 0.88, 0.07], "#FFFFFF", "#CBD5E1"),
            _shape("risk_row_04", "primary_content_grid", [0.06, 0.52, 0.88, 0.07], "#EFF6FF", "#CBD5E1"),
            _shape("risk_status_rail", "right_side_rail", [0.78, 0.21, 0.16, 0.54], "#0F172A", "#F59E0B"),
            _shape("risk_header_band", "title_cluster", [0.04, 0.06, 0.92, 0.10], "#0B1528", "#F59E0B"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.03, 0.88, 0.94, 0.07], "#111827", "#38BDF8"),
        ],
        "case_study": [
            _crop("case_visual_field", "hero_visual_field", [0.05, 0.20, 0.36, 0.55], reference_image_path, "bounded case visual field"),
            _shape("case_context_panel", "card_panel_group", [0.45, 0.18, 0.50, 0.58], "#F8FAFC", "#CBD5E1"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.03, 0.88, 0.94, 0.07], "#111827", "#38BDF8"),
        ],
        "closing_synthesis": [
            _shape("recommendation_panel", "card_panel_group", [0.08, 0.20, 0.52, 0.48], "#F8FAFC", "#CBD5E1"),
            _shape("next_action_rail", "right_side_rail", [0.66, 0.18, 0.26, 0.55], "#0F172A", "#F59E0B"),
            _shape("footer_source_strip", "bottom_footer_source_strip", [0.03, 0.88, 0.94, 0.07], "#111827", "#38BDF8"),
        ],
    }
    regions = skeletons.get(reference_id, [])
    for region in regions:
        region["region_id"] = f"{reference_id}_{region['region_id']}"
        region["reference_id"] = reference_id
        region["source"] = "archetype_composition_skeleton"
    return regions


def _missing_required(reference_id: str, regions: list[dict[str, Any]]) -> list[str]:
    present = {region["major_region_type"] for region in regions}
    return sorted(set(_required_types(reference_id)).difference(present))


def _required_types(reference_id: str) -> list[str]:
    if reference_id == "canva_benchmark":
        return ["hero_visual_field", "primary_content_grid", "bottom_footer_source_strip"]
    if reference_id == "cover_hero":
        return ["hero_visual_field", "title_cluster", "bottom_footer_source_strip"]
    if reference_id == "data_dashboard":
        return ["chart_frame", "right_side_rail", "bottom_footer_source_strip"]
    if reference_id == "table_heavy":
        return ["table_frame", "bottom_footer_source_strip"]
    if reference_id == "section_divider":
        return ["hero_visual_field", "title_cluster", "bottom_footer_source_strip"]
    if reference_id in {"visual_toc", "methodology_framework", "process_flow", "timeline_roadmap"}:
        return ["primary_content_grid", "card_panel_group", "bottom_footer_source_strip"]
    if reference_id in {"comparison_matrix", "risk_register"}:
        return ["table_frame", "bottom_footer_source_strip"]
    if reference_id in {"evidence_overview", "decision_record", "closing_synthesis"}:
        return ["card_panel_group", "right_side_rail", "bottom_footer_source_strip"]
    if reference_id == "case_study":
        return ["hero_visual_field", "card_panel_group", "bottom_footer_source_strip"]
    return ["card_panel_group", "bottom_footer_source_strip"]


def _shape_region(reference_id: str, region_type: str, layer: dict[str, Any], fill: str, line: str) -> dict[str, Any]:
    return {
        "region_id": f"{reference_id}_{region_type}_{layer.get('layer_id')}",
        "reference_id": reference_id,
        "major_region_type": region_type,
        "object_type": "ppt_shape",
        "bbox_norm": layer.get("bbox_norm"),
        "bbox_px": layer.get("bbox_px"),
        "source_layer_ids": [layer.get("layer_id")],
        "source": "layer_manifest_v4",
        "fill": fill,
        "line": line,
        "z_order": 80,
        "editable": True,
    }


def _scoped_crop_region(reference_id: str, region_type: str, layer: dict[str, Any]) -> dict[str, Any]:
    return {
        "region_id": f"{reference_id}_{region_type}_{layer.get('layer_id')}",
        "reference_id": reference_id,
        "major_region_type": region_type,
        "object_type": "scoped_visual_field_crop",
        "bbox_norm": layer.get("bbox_norm"),
        "bbox_px": layer.get("bbox_px"),
        "source_crop_bbox_norm": layer.get("bbox_norm"),
        "source_layer_ids": [layer.get("layer_id")],
        "source": "layer_manifest_v4",
        "z_order": 30,
        "editable": True,
        "notes": "Scoped visual field crop for nonsemantic visual preservation.",
    }


def _shape(region_id: str, region_type: str, bbox_norm: list[float], fill: str, line: str) -> dict[str, Any]:
    return {
        "region_id": region_id,
        "major_region_type": region_type,
        "object_type": "ppt_shape",
        "bbox_norm": bbox_norm,
        "source_layer_ids": [],
        "fill": fill,
        "line": line,
        "z_order": 80,
        "editable": True,
    }


def _crop(region_id: str, region_type: str, bbox_norm: list[float], reference_image_path: Path, notes: str) -> dict[str, Any]:
    return {
        "region_id": region_id,
        "major_region_type": region_type,
        "object_type": "scoped_visual_field_crop",
        "bbox_norm": bbox_norm,
        "source_crop_bbox_norm": bbox_norm,
        "source_image_path": reference_image_path.as_posix(),
        "source_layer_ids": [],
        "z_order": 30,
        "editable": True,
        "notes": notes,
    }


def _area(bbox_norm: Any) -> float:
    if not isinstance(bbox_norm, list) or len(bbox_norm) != 4:
        return 0.0
    return float(bbox_norm[2]) * float(bbox_norm[3])
