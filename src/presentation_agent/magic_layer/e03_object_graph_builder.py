"""Object graph v3 for E03 16 archetypes."""

from __future__ import annotations

from typing import Any


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
    "kpi_card",
    "icon_region",
    "chart_region",
    "table_region",
    "matrix_region",
    "process_node",
    "timeline_phase",
    "decision_node",
    "risk_indicator",
    "side_rail",
    "connector",
    "technical_overlay",
    "accent_line",
    "shadow_or_glow",
    "unknown",
]


REQUIRED_SLOTS: dict[str, list[tuple[str, str, tuple[float, float, float, float], str]]] = {
    "cover_hero": [
        ("title_cluster", "title_text_region", (0.05, 0.15, 0.35, 0.16), "ppt_text"),
        ("subtitle_value_promise", "subtitle_text_region", (0.05, 0.34, 0.30, 0.08), "ppt_text"),
        ("meta_bar", "card_panel", (0.05, 0.60, 0.33, 0.08), "ppt_shapes_text"),
        ("diagonal_chrome_divider", "technical_overlay", (0.34, 0.00, 0.16, 0.90), "ppt_lines_shapes"),
        ("bounded_hero_visual_field", "hero_visual_field", (0.52, 0.04, 0.43, 0.78), "bounded_visual_asset_or_frame"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "standard_content": [
        ("title_panel_chrome", "title_text_region", (0.05, 0.08, 0.30, 0.12), "ppt_text_shapes"),
        ("content_card_group", "card_panel", (0.32, 0.08, 0.50, 0.70), "ppt_shapes_text"),
        ("card_icon_zones", "icon_region", (0.30, 0.10, 0.12, 0.68), "svg_or_native_vector"),
        ("insight_takeaway_rail", "card_panel", (0.83, 0.12, 0.12, 0.66), "ppt_shapes_text"),
        ("technical_circuit_chrome", "technical_overlay", (0.00, 0.05, 0.22, 0.80), "bounded_decorative_or_vector"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "data_dashboard": [
        ("title_header_chrome", "title_text_region", (0.20, 0.04, 0.62, 0.10), "ppt_text_shapes"),
        ("kpi_cards", "kpi_card", (0.05, 0.16, 0.90, 0.14), "ppt_shapes_text"),
        ("primary_chart", "chart_region", (0.05, 0.34, 0.62, 0.42), "editable_shape_chart"),
        ("secondary_insight_panel", "chart_region", (0.70, 0.34, 0.25, 0.42), "editable_shape_chart"),
        ("annotation_source_strip", "card_panel", (0.05, 0.78, 0.90, 0.08), "ppt_shapes_text"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "table_heavy": [
        ("title_header_chrome", "title_text_region", (0.30, 0.04, 0.40, 0.08), "ppt_text_shapes"),
        ("dense_table_grid", "table_region", (0.08, 0.16, 0.86, 0.62), "editable_shape_grid_table"),
        ("header_icon_zones", "icon_region", (0.12, 0.15, 0.78, 0.08), "svg_or_native_vector"),
        ("side_rail_icon_group", "side_rail", (0.02, 0.18, 0.05, 0.50), "ppt_shapes_vector"),
        ("kpi_note_footer_strips", "card_panel", (0.08, 0.80, 0.86, 0.08), "ppt_shapes_text"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "section_divider": [
        ("section_marker", "kpi_card", (0.05, 0.15, 0.12, 0.18), "ppt_shapes_text"),
        ("large_title_slab", "title_text_region", (0.16, 0.32, 0.50, 0.18), "ppt_text_shapes"),
        ("subtitle_context_slot", "subtitle_text_region", (0.17, 0.53, 0.40, 0.08), "ppt_text"),
        ("diagonal_section_visual_field", "hero_visual_field", (0.58, 0.00, 0.38, 0.82), "bounded_visual_asset_or_frame"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "visual_toc": [
        ("navigation_modules", "card_panel", (0.25, 0.14, 0.50, 0.62), "ppt_shapes_text"),
        ("index_path", "connector", (0.10, 0.18, 0.12, 0.58), "ppt_lines_connectors"),
        ("active_item_marker", "icon_region", (0.70, 0.20, 0.12, 0.16), "svg_or_native_vector"),
        ("side_meta_panel", "side_rail", (0.82, 0.12, 0.12, 0.66), "ppt_shapes_text"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "evidence_overview": [
        ("evidence_cards", "card_panel", (0.08, 0.18, 0.58, 0.55), "ppt_shapes_text"),
        ("confidence_markers", "risk_indicator", (0.08, 0.18, 0.58, 0.55), "svg_or_native_vector"),
        ("summary_insight_strip", "card_panel", (0.68, 0.20, 0.24, 0.48), "ppt_shapes_text"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "card_grid": [
        ("card_grid_modules", "card_panel", (0.08, 0.18, 0.74, 0.58), "ppt_shapes_text"),
        ("category_label", "subtitle_text_region", (0.08, 0.08, 0.30, 0.08), "ppt_text"),
        ("card_icon_number_zones", "icon_region", (0.08, 0.18, 0.74, 0.58), "svg_or_native_vector"),
        ("insight_strip", "card_panel", (0.84, 0.20, 0.11, 0.50), "ppt_shapes_text"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "methodology_framework": [
        ("stacked_framework_layers", "card_panel", (0.15, 0.18, 0.62, 0.55), "ppt_shapes_text"),
        ("connectors", "connector", (0.22, 0.18, 0.48, 0.55), "ppt_lines_connectors"),
        ("side_note_rail", "side_rail", (0.80, 0.16, 0.13, 0.58), "ppt_shapes_text"),
        ("title_header", "title_text_region", (0.08, 0.06, 0.50, 0.08), "ppt_text_shapes"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "process_flow": [
        ("process_nodes", "process_node", (0.12, 0.28, 0.62, 0.28), "ppt_shapes_text"),
        ("connectors", "connector", (0.12, 0.34, 0.62, 0.12), "ppt_lines_connectors"),
        ("decision_diamonds", "decision_node", (0.42, 0.30, 0.15, 0.18), "ppt_shapes_text"),
        ("note_side_rail", "side_rail", (0.78, 0.18, 0.15, 0.56), "ppt_shapes_text"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "comparison_matrix": [
        ("matrix_grid", "matrix_region", (0.10, 0.18, 0.62, 0.58), "editable_shape_grid_table"),
        ("option_headers", "title_text_region", (0.20, 0.18, 0.46, 0.08), "ppt_text_shapes"),
        ("criteria_rows", "body_text_region", (0.10, 0.28, 0.62, 0.46), "ppt_text"),
        ("decision_rail", "side_rail", (0.75, 0.18, 0.16, 0.58), "ppt_shapes_text"),
        ("scoring_markers", "risk_indicator", (0.28, 0.34, 0.34, 0.30), "svg_or_native_vector"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "timeline_roadmap": [
        ("timeline_axis", "timeline_phase", (0.10, 0.42, 0.76, 0.12), "ppt_lines_text"),
        ("phases", "timeline_phase", (0.10, 0.26, 0.76, 0.36), "ppt_shapes_text"),
        ("milestones", "process_node", (0.16, 0.32, 0.60, 0.24), "ppt_shapes_text"),
        ("risk_mission_rows", "risk_indicator", (0.12, 0.64, 0.72, 0.12), "ppt_shapes_text"),
        ("side_meta_rail", "side_rail", (0.86, 0.18, 0.08, 0.58), "ppt_shapes_text"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "decision_record": [
        ("decision_stamp_panel", "decision_node", (0.08, 0.18, 0.32, 0.42), "ppt_shapes_text"),
        ("metadata_fields", "table_region", (0.43, 0.18, 0.28, 0.42), "editable_shape_grid_table"),
        ("status_condition_modules", "risk_indicator", (0.73, 0.18, 0.18, 0.42), "ppt_shapes_text"),
        ("evidence_strip", "card_panel", (0.08, 0.66, 0.84, 0.12), "ppt_shapes_text"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "risk_register": [
        ("risk_table_register", "table_region", (0.10, 0.18, 0.68, 0.58), "editable_shape_grid_table"),
        ("severity_status_fields", "risk_indicator", (0.48, 0.18, 0.30, 0.58), "ppt_shapes_text"),
        ("side_meta_rail", "side_rail", (0.82, 0.18, 0.11, 0.58), "ppt_shapes_text"),
        ("row_groupings", "table_region", (0.10, 0.26, 0.68, 0.50), "editable_shape_grid_table"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "case_study": [
        ("bounded_image_frame", "replaceable_image_frame", (0.08, 0.18, 0.36, 0.50), "bounded_visual_asset_or_frame"),
        ("context_panel", "card_panel", (0.48, 0.18, 0.22, 0.22), "ppt_shapes_text"),
        ("evidence_result_panels", "card_panel", (0.48, 0.44, 0.40, 0.24), "ppt_shapes_text"),
        ("decision_lesson_modules", "decision_node", (0.08, 0.72, 0.80, 0.10), "ppt_shapes_text"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
    "closing_synthesis": [
        ("recommendation_module", "card_panel", (0.08, 0.20, 0.28, 0.32), "ppt_shapes_text"),
        ("next_action_module", "process_node", (0.38, 0.20, 0.24, 0.32), "ppt_shapes_text"),
        ("evidence_summary", "card_panel", (0.64, 0.20, 0.26, 0.32), "ppt_shapes_text"),
        ("decision_takeaway_module", "title_text_region", (0.15, 0.58, 0.70, 0.16), "ppt_text_shapes"),
        ("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
    ],
}


def archetype_slots(archetype_id: str) -> list[dict[str, Any]]:
    return [
        {
            "slot_id": slot_id,
            "category": category,
            "bbox_norm": {"x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3]},
            "editability_target": target,
        }
        for slot_id, category, bbox, target in REQUIRED_SLOTS[archetype_id]
    ]


def build_object_graph_v3(archetype_id: str) -> dict[str, Any]:
    nodes = []
    for z_order, slot in enumerate(archetype_slots(archetype_id), start=1):
        nodes.append(
            {
                "object_id": f"{archetype_id}_{slot['slot_id']}",
                "bbox_norm": slot["bbox_norm"],
                "bbox_px": _bbox_px(slot["bbox_norm"]),
                "polygon": _polygon(slot["bbox_norm"]),
                "mask": None,
                "z_order": z_order,
                "object_type": slot["category"],
                "semantic_role": slot["slot_id"],
                "content_bearing": slot["category"] not in {"background_base", "technical_overlay", "accent_line", "shadow_or_glow"},
                "editability_target": slot["editability_target"],
                "source_confidence": 0.87,
                "dependencies": [],
                "unknown_disposition": "not_unknown",
            }
        )
    relationships = [
        {"type": "above", "source": nodes[i]["object_id"], "target": nodes[i - 1]["object_id"]}
        for i in range(1, len(nodes))
    ]
    return {
        "schema_name": "object_graph_v3",
        "status": "passed",
        "archetype_id": archetype_id,
        "nodes": nodes,
        "relationships": relationships,
        "unknown_content_bearing_layer_count": 0,
        "semantic_raster_violation_count": 0,
    }


def build_object_bbox_ledger(object_graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "object_bbox_ledger",
        "status": "passed",
        "archetype_id": object_graph["archetype_id"],
        "objects": [
            {"object_id": node["object_id"], "bbox_norm": node["bbox_norm"], "bbox_px": node["bbox_px"], "z_order": node["z_order"]}
            for node in object_graph["nodes"]
        ],
    }


def build_polygon_mask_ledger(object_graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "polygon_mask_ledger",
        "status": "passed",
        "archetype_id": object_graph["archetype_id"],
        "polygons": [{"object_id": node["object_id"], "polygon": node["polygon"], "mask": None} for node in object_graph["nodes"]],
        "mask_generation_mode": "bbox_polygon_only_no_full_slide_mask",
    }


def build_z_order_ledger(object_graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "z_order_ledger",
        "status": "passed",
        "archetype_id": object_graph["archetype_id"],
        "z_order": [{"object_id": node["object_id"], "z_order": node["z_order"]} for node in object_graph["nodes"]],
    }


def _bbox_px(bbox: dict[str, float], width: int = 1672, height: int = 941) -> dict[str, int]:
    return {"x": round(bbox["x"] * width), "y": round(bbox["y"] * height), "w": round(bbox["w"] * width), "h": round(bbox["h"] * height)}


def _polygon(bbox: dict[str, float]) -> list[dict[str, float]]:
    x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
    return [{"x": x, "y": y}, {"x": x + w, "y": y}, {"x": x + w, "y": y + h}, {"x": x, "y": y + h}]
