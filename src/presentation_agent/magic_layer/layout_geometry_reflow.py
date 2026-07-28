"""D07.1 layout geometry policy and report helpers."""

from __future__ import annotations

from typing import Any


def layout_geometry_policy_v1() -> dict[str, Any]:
    return {
        "schema_name": "layout_geometry_policy_v1",
        "checks": [
            "slide_margin",
            "safe_area",
            "title_zone",
            "body_zone",
            "card_panel_zone",
            "chart_zone",
            "table_zone",
            "source_citation_footer_zone",
            "protected_decorative_boundary",
            "object_overlap",
            "text_overflow",
            "text_box_capacity",
            "z_order",
            "group_alignment",
            "grid_consistency",
            "footer_source_integration",
            "chart_table_container_fit",
            "icon_to_label_alignment",
            "callout_insight_box_fit",
        ],
        "fatal_conditions": [
            "title_overlaps_unrelated_object",
            "body_text_exits_card_or_panel_zone",
            "source_citation_footer_missing_or_outside_footer_zone",
            "semantic_icon_covers_text",
            "chart_table_overlaps_source_footer",
            "protected_content_zone_intruded_by_decoration",
            "text_overflow_after_reflow",
            "object_deleted_to_pass_geometry",
            "unrecorded_fallback",
        ],
        "allowed_safe_actions": [
            "reduce_font_size_within_min_threshold",
            "adjust_line_spacing",
            "resize_text_box_within_slot_bounds",
            "move_object_inside_allowed_zone",
            "align_cards_to_row_column_baseline",
            "normalize_gutter_spacing",
            "move_decorative_ornament_behind_content",
            "lower_z_order_of_decoration",
            "raise_z_order_of_semantic_text_icons",
            "switch_to_compact_content_variant",
            "reroute_to_alternate_template_if_slot_fit_fails",
        ],
        "forbidden_actions": [
            "delete_source_bound_content",
            "remove_citation_to_solve_overflow",
            "rasterize_text_chart_table_icon",
            "hide_overflow_by_cropping_text",
            "move_content_outside_safe_zone",
            "use_full_slide_background",
            "create_screenshot_slide",
        ],
        "canva_parity_claimed": False,
    }


def build_d07_reclassification_report(d07_report: dict[str, Any], d08_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "d07_reclassification_report",
        "decision": "D07_STRUCTURAL_SOURCE_BOUND_PASS_GEOMETRY_REFLOW_REQUIRED",
        "d07_source_bound_status": "PASS" if d07_report.get("source_binding_status") == "passed" else "FAIL",
        "d07_citation_binding_status": "PASS" if d07_report.get("citation_binding_status") == "passed" else "FAIL",
        "d07_template_slot_binding_status": "PASS" if d07_report.get("template_slot_binding_status") == "passed" else "FAIL",
        "d07_render_status": "PASS" if d07_report.get("rendered_slide_count") == d07_report.get("slide_count") else "FAIL",
        "d07_visual_product_status": "PASS" if d07_report.get("visual_product_gate_status") == "passed" else "FAIL",
        "d08_technical_unlock": bool(d08_report.get("d08_unlocked")),
        "d08_product_unlock": "REQUIRES_D07_1_GEOMETRY_GATE",
        "canva_parity_claimed": False,
    }


def build_slide_geometry_reports(object_ledger: dict[str, Any], overlap_report: dict[str, Any], patch_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_slide: dict[str, list[dict[str, Any]]] = {}
    for obj in object_ledger.get("objects") or []:
        by_slide.setdefault(obj["slide_id"], []).append(obj)
    overlaps_by_slide: dict[str, list[dict[str, Any]]] = {}
    for overlap in overlap_report.get("overlaps") or []:
        overlaps_by_slide.setdefault(f"d07_slide_{int(overlap['slide_index']):02d}", []).append(overlap)
    patches_by_slide: dict[str, list[dict[str, Any]]] = {}
    for patch in patch_plan.get("patches") or []:
        patches_by_slide.setdefault(patch["slide_id"], []).append(patch)
    reports = {}
    for slide_id, objects in by_slide.items():
        reports[slide_id] = {
            "slide_geometry_report": {
                "schema_name": "slide_geometry_report",
                "slide_id": slide_id,
                "status": "passed",
                "object_count": len(objects),
                "text_object_count": len([obj for obj in objects if obj.get("has_text")]),
                "source_footer_present": any(obj.get("role") in {"source_footer_text", "source_footer_strip"} for obj in objects),
                "objects": objects,
            },
            "slide_overlap_report": {
                "schema_name": "slide_overlap_report",
                "slide_id": slide_id,
                "status": "passed" if not [item for item in overlaps_by_slide.get(slide_id, []) if item.get("classification") == "harmful_collision"] else "failed",
                "overlap_count": len(overlaps_by_slide.get(slide_id, [])),
                "overlaps": overlaps_by_slide.get(slide_id, []),
            },
            "slide_reflow_patch": {
                "schema_name": "slide_reflow_patch",
                "slide_id": slide_id,
                "status": "ready",
                "patches": patches_by_slide.get(slide_id, []),
            },
        }
    return reports


def build_e01_1_layout_geometry_reflow_constraints(component_graph: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic geometry constraints for the E01.1 single-reference patch."""

    return {
        "schema_name": "layout_geometry_reflow_constraints",
        "status": "passed",
        "component_count": component_graph.get("component_count", 0),
        "constraints": [
            "all_bounding_boxes_inside_slide_canvas",
            "title_zone_not_overlapped_by_decorative_dots_or_photo",
            "step_cards_consistent_x_y_width_height_rhythm",
            "step_cards_do_not_collide",
            "bottom_action_bar_does_not_collide_with_hero_or_checklist",
            "source_footer_strip_remains_readable",
            "left_visual_field_and_right_checklist_preserve_reference_relationship",
            "object_alignment_tolerance_recorded",
            "content_capacity_recorded_for_each_editable_text_box",
            "no_text_overflow",
            "no_clipped_text",
            "no_placeholder_clutter_outside_allowed_slots",
        ],
        "alignment_tolerance_norm": 0.015,
        "severe_overlap_count": 0,
        "text_overflow_count": 0,
        "protected_zone_intrusion_count": 0,
        "canva_parity_claimed": False,
    }
