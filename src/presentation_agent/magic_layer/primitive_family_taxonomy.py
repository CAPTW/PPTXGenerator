"""PPT-native primitive family taxonomy for Magic Layer D03."""

from __future__ import annotations

from typing import Any


PRIMITIVE_FAMILIES = {
    "background_base": ("ppt_shape", "ppt_shape", "no_full_slide_reference_background"),
    "hero_visual_field": ("replaceable_image_frame", "replaceable_image_frame", "scoped_visual_raster_allowed_after_D05"),
    "replaceable_image_frame": ("replaceable_image_frame", "replaceable_image_frame", "scoped_visual_raster_allowed_after_D05"),
    "diagonal_image_mask": ("ppt_freeform_shape", "replaceable_image_frame", "scoped_visual_raster_allowed_after_D05"),
    "crop_mask_frame": ("ppt_freeform_shape", "ppt_shape", "no_semantic_raster"),
    "title_text_region": ("ppt_text", "ppt_text", "text_must_be_editable"),
    "body_text_region": ("ppt_text", "ppt_text", "text_must_be_editable"),
    "section_marker": ("ppt_shape", "ppt_shape", "no_semantic_raster"),
    "card_panel": ("ppt_shape", "ppt_shape", "no_semantic_raster"),
    "evidence_card": ("ppt_shape", "ppt_shape", "no_semantic_raster"),
    "kpi_card": ("ppt_shape", "ppt_shape", "no_semantic_raster"),
    "insight_panel": ("ppt_shape", "ppt_shape", "no_semantic_raster"),
    "source_footer_strip": ("ppt_shape", "ppt_shape", "must_remain_editable"),
    "technical_overlay": ("ppt_line", "ppt_shape", "decorative_shape_or_vector_only"),
    "accent_line": ("ppt_line", "ppt_shape", "decorative_shape_or_vector_only"),
    "connector_line": ("ppt_connector", "ppt_shape", "editable_connector_required"),
    "process_node": ("ppt_shape", "ppt_shape", "no_semantic_raster"),
    "decision_diamond": ("ppt_shape", "ppt_shape", "no_semantic_raster"),
    "timeline_phase": ("ppt_shape", "ppt_shape", "no_semantic_raster"),
    "milestone_marker": ("ppt_shape", "ppt_shape", "no_semantic_raster"),
    "matrix_region": ("editable_table_pending_D04", "editable_table", "handoff_D04_required"),
    "comparison_matrix_grid": ("editable_table_pending_D04", "editable_table", "handoff_D04_required"),
    "table_region": ("editable_table_pending_D04", "editable_table", "handoff_D04_required"),
    "chart_region": ("editable_chart_pending_D04", "editable_chart", "handoff_D04_required"),
    "chart_frame": ("ppt_shape", "ppt_shape", "handoff_D04_required"),
    "legend_group": ("ppt_shape", "ppt_shape", "handoff_D04_required"),
    "axis_label_group": ("ppt_text", "ppt_text", "handoff_D04_required"),
    "side_rail": ("ppt_shape", "ppt_shape", "no_semantic_raster"),
    "callout_panel": ("ppt_shape", "ppt_shape", "no_semantic_raster"),
    "note_panel": ("ppt_shape", "ppt_shape", "no_semantic_raster"),
    "unknown_primitive": ("reject_or_patch", "reject_or_patch", "unknown_must_be_disposed"),
}


def build_primitive_family_taxonomy() -> dict[str, Any]:
    families = []
    for family, (ppt_type, editability, raster_policy) in PRIMITIVE_FAMILIES.items():
        families.append(
            {
                "primitive_family": family,
                "target_ppt_implementation": ppt_type,
                "expected_layer_types": _expected_layer_types(family),
                "allowed_editability_target": editability,
                "raster_policy": raster_policy,
                "D04_handoff_requirement": "required" if "D04" in raster_policy or family in {"chart_region", "table_region", "matrix_region", "comparison_matrix_grid"} else "not_required",
                "D05_render_fidelity_requirement": "render_compare_required",
                "failure_conditions": _failure_conditions(family),
            }
        )
    return {"schema_name": "primitive_family_taxonomy_v1", "status": "passed", "families": families, "family_count": len(families)}


def family_spec(taxonomy: dict[str, Any], family: str) -> dict[str, Any] | None:
    for item in taxonomy.get("families") or []:
        if item["primitive_family"] == family:
            return item
    return None


def _expected_layer_types(family: str) -> list[str]:
    mapping = {
        "source_footer_strip": ["source_footer_strip"],
        "connector_line": ["connector"],
        "technical_overlay": ["technical_overlay"],
        "accent_line": ["accent_line"],
        "table_region": ["table_region"],
        "matrix_region": ["matrix_region"],
        "chart_region": ["chart_region"],
        "card_panel": ["card_panel"],
        "title_text_region": ["title_text_region"],
        "body_text_region": ["body_text_region", "subtitle_text_region"],
        "background_base": ["background_base"],
    }
    return mapping.get(family, [family])


def _failure_conditions(family: str) -> list[str]:
    base = ["unrecorded_fallback", "unallowlisted_fallback"]
    if family in {"chart_region", "table_region", "matrix_region", "comparison_matrix_grid"}:
        return base + ["semantic_component_rasterized", "missing_D04_handoff"]
    if family == "source_footer_strip":
        return base + ["classified_as_decorative", "non_editable_source_footer"]
    if family == "unknown_primitive":
        return base + ["unknown_silently_passed"]
    return base

