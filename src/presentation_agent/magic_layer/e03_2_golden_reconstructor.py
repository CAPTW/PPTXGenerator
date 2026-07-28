"""Golden reconstruction plan for the selected E03.2 slide."""

from __future__ import annotations

from typing import Any


def build_e03_2_patch_plan(target_report: dict[str, Any], analysis: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e03_2_patch_plan",
        "status": "planned",
        "target_archetype": target_report["target_archetype"],
        "reference_analysis_regions": len(analysis["major_regions"]),
        "object_graph_nodes": len(graph["nodes"]),
        "actions": [
            "rebuild_dark_header_and_title_cluster",
            "restore_white_main_stage_with_notched_top_rule",
            "place_six_vertical_navigation_cards",
            "restore_02_active_gold_state",
            "restore_progress_path_and_reading_path_connectors",
            "restore_right_metadata_panel",
            "restore_footer_source_system",
            "validate_bbox_iou_z_order_collision_text_capacity",
        ],
        "no_full_slide_raster": True,
        "semantic_raster_forbidden": True,
        "source_bound_deck_created": False,
        "e04_started": False,
    }


def build_reconstruction_plan(graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e03_2_golden_reconstruction_plan",
        "status": "passed",
        "target_archetype": graph["target_archetype"],
        "object_ids": [node["object_id"] for node in graph["nodes"]],
        "placement_basis": "reference_analysis_bbox_norm",
        "semantic_text_as_ppt_text": True,
        "semantic_icons_as_native_vector": True,
        "cards_panels_footer_as_ppt_shapes": True,
        "connectors_as_ppt_lines": True,
        "bounded_raster_count": 0,
    }
