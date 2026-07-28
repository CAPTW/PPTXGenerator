"""Canva Magic Layer+ object conversion gate requirements."""

from __future__ import annotations

from typing import Any


REQUIRED_OBJECT_GRAPH_ARTIFACTS = [
    "reference_image.png",
    "object_graph_v1.json",
    "layer_manifest_v5.json",
    "semantic_slot_graph.json",
    "visual_layer_graph.json",
    "object_bbox_ledger.json",
    "polygon_mask_ledger.json",
    "z_order_ledger.json",
    "text_region_ledger.json",
    "image_field_ledger.json",
    "icon_region_ledger.json",
    "chart_table_region_ledger.json",
    "native_reconstruction_plan.json",
    "editable_candidate_spec.json",
    "editable_candidate.pptx",
    "rendered_candidate.png",
    "reference_vs_render.png",
    "visual_similarity_metrics.json",
    "semantic_editability_ledger.json",
    "canva_plus_gate_report.json",
]


LAYER_CATEGORIES = [
    "background_base",
    "hero_visual_field",
    "replaceable_image_frame",
    "decorative_texture",
    "title_text_region",
    "subtitle_text_region",
    "body_text_region",
    "source_footer_strip",
    "card_panel",
    "checklist_panel",
    "icon_region",
    "chart_region",
    "table_region",
    "matrix_region",
    "process_node",
    "timeline_phase",
    "connector",
    "technical_overlay",
    "accent_line",
    "shadow_or_glow",
    "unknown",
]


def build_image_to_editable_object_graph_requirements_v1() -> dict[str, Any]:
    return {
        "schema_name": "image_to_editable_object_graph_requirements_v1",
        "product_unit": "reference image -> editable PPT layer conversion",
        "required_artifacts": REQUIRED_OBJECT_GRAPH_ARTIFACTS,
        "layer_categories": LAYER_CATEGORIES,
        "unknown_policy": {
            "unknown_content_bearing_layer": "fatal",
            "unknown_semantic_layer": "fatal_or_explicit_reject",
            "decorative_unknown": "bounded_only_with_reason",
        },
        "full_slide_reference_background_allowed": False,
        "screenshot_slide_allowed": False,
        "canva_parity_claimed": False,
    }


def build_semantic_native_reconstruction_requirements_v1() -> dict[str, Any]:
    return {
        "schema_name": "semantic_native_reconstruction_requirements_v1",
        "rules": {
            "text": "ppt_text_box_required",
            "semantic_icons": "svg_or_vector_required",
            "charts": "native_chart_or_editable_shape_chart_required",
            "tables": "native_table_or_editable_shape_grid_table_required",
            "cards_panels": "ppt_shapes_and_text_required",
            "source_footer_citation": "ppt_text_and_shape_required",
            "connectors": "ppt_connector_line_or_freeform_required",
            "hero_photo_visual_field": "replaceable_image_frame_or_bounded_scoped_visual_asset_allowed",
            "decorative_texture": "bounded_raster_or_vector_allowed",
            "full_slide_raster": "forbidden",
            "screenshot_slide": "forbidden",
            "semantic_raster_final_use": "forbidden",
            "raster_fallback": "recorded_and_allowlisted_only_for_non_semantic_visual_fields",
        },
        "canva_parity_claimed": False,
    }


def evaluate_magic_layer_plus_gate(candidate: dict[str, Any]) -> dict[str, Any]:
    missing = [name for name in REQUIRED_OBJECT_GRAPH_ARTIFACTS if name not in set(candidate.get("artifacts", []))]
    failures: list[str] = []
    if missing:
        failures.append("missing_required_object_graph_artifacts")
    if candidate.get("full_slide_raster") is True:
        failures.append("full_slide_raster_forbidden")
    if candidate.get("screenshot_slide") is True:
        failures.append("screenshot_slide_forbidden")
    if candidate.get("semantic_raster_icon_chart_table_count", 0) > 0:
        failures.append("semantic_raster_icon_chart_table_forbidden")
    if candidate.get("unknown_content_bearing_layer_count", 0) > 0:
        failures.append("unknown_content_bearing_layer_fatal")
    if candidate.get("semantic_text_editable") is not True:
        failures.append("semantic_text_not_editable")
    if candidate.get("object_graph_exists") is not True:
        failures.append("object_graph_missing")
    if candidate.get("reference_vs_render_fidelity") not in {"acceptable", "pass", "strong"}:
        failures.append("reference_vs_render_fidelity_not_acceptable")
    return {
        "schema_name": "canva_plus_gate_report",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "missing_artifacts": missing,
        "canva_parity_claimed": False,
    }


def build_e01_single_reference_conversion_gate_spec() -> dict[str, Any]:
    return {
        "schema_name": "e01_single_reference_conversion_gate_spec",
        "scope": {
            "primary_gate_reference": "design_runs/benchmarks/canva_magic_layer/assets/reference_image.png",
            "secondary_gate_reference_optional": "one generated Harness reference image",
            "source_bound_deck_created": False,
            "large_deck_created": False,
            "conversion_unit": "one reference image into one editable PPT candidate",
        },
        "required_conditions": [
            "object_graph_v1_exists",
            "layer_manifest_v5_exists",
            "semantic_slot_graph_exists",
            "editable_candidate_pptx_exists",
            "candidate_renders",
            "no_full_slide_reference_background",
            "no_screenshot_slide",
            "semantic_text_editable",
            "semantic_icons_svg_vector_or_not_present",
            "semantic_charts_tables_native_editable_or_not_applicable",
            "cards_panels_source_footer_as_ppt_shapes_text",
            "visual_layer_count_comparable_to_or_richer_than_canva_where_relevant",
            "reference_vs_render_fidelity_acceptable",
            "unknown_content_bearing_layers_zero",
            "semantic_raster_violations_zero",
            "ocr_text_risk_bounded_or_blocked",
            "mask_polygon_fidelity_bounded_or_pass",
            "no_critical_blockers",
            "no_high_product_risks",
        ],
        "decisions": [
            "E01_PASS_START_E02_4CORE_MAGIC_LAYER_PLUS",
            "E01_PATCH_OBJECT_GRAPH_EXTRACTION",
            "E01_PATCH_TEXT_REGION_LIFT",
            "E01_PATCH_NATIVE_COMPONENT_RECONSTRUCTION",
            "E01_PATCH_RENDER_FIDELITY",
            "E01_FAIL_CANVA_LAYER_TARGET",
            "E01_FAIL_SEMANTIC_EDITABILITY",
            "E01_FAIL_PROTECTED_ARTIFACTS",
        ],
        "canva_parity_claimed": False,
    }
