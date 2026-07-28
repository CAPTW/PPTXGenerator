"""E03.3 object placement policy derived from the E03.2 golden slide gate."""

from __future__ import annotations

from typing import Any


def build_object_placement_policy() -> dict[str, Any]:
    thresholds = {
        "title_header_region_drift": 0.05,
        "main_content_region_iou": 0.70,
        "footer_source_region_drift": 0.04,
        "side_rail_meta_region_drift": 0.06,
        "chart_table_process_timeline_region_iou": 0.68,
        "card_group_region_iou": 0.70,
        "semantic_object_collision_count": 0,
        "text_overflow_count": 0,
        "text_clipping_count": 0,
        "z_order_fatal_inversion_count": 0,
        "semantic_raster_violation_count": 0,
        "full_slide_raster_count": 0,
        "screenshot_slide_count": 0,
    }
    return {
        "schema_name": "e03_3_object_placement_policy_v1",
        "status": "passed",
        "golden_source": "E03.2 visual_toc single-slide golden object placement gate",
        "thresholds": thresholds,
        "forbidden": {
            "full_slide_reference_background": True,
            "screenshot_slide": True,
            "semantic_raster_icon": True,
            "quarantined_svg": True,
            "generic_plus_placeholder_for_semantic_role": True,
            "unknown_content_bearing_layer": True,
            "generic_skeleton_collapse": True,
        },
        "mandatory_checks": [
            "major_region_bbox_drift",
            "region_iou",
            "object_collision",
            "z_order_inversion",
            "semantic_slot_coverage",
            "text_capacity",
            "icon_vector_validity",
            "chart_table_component_validity",
            "raster_policy",
            "unknown_content_bearing_layer_policy",
            "reference_specific_visual_grammar",
        ],
        "threshold_exception_policy": "explicit_report_only_no_silent_loosening",
    }
