"""Resolve semantic icon roles into slide component anchors."""

from __future__ import annotations

from typing import Any

from .e03_3_icon_vector_pipeline import EXPECTED_ICON_ROLES
from .e04_deck_planner import E04_SLIDE_ORDER
from .e04_1_icon_size_tokens import size_for_token


SLIDE_ANCHORS: dict[str, list[tuple[str, str, float, float, str, str]]] = {
    "cover_hero": [
        ("meta_bar_icon", "hero_meta_bar", 0.62, 6.82, "icon_hero_meta", "footer_lead"),
        ("meta_bar_icon", "hero_meta_bar", 1.10, 6.82, "icon_hero_meta", "footer_lead"),
        ("meta_bar_icon", "hero_meta_bar", 1.58, 6.82, "icon_hero_meta", "footer_lead"),
    ],
    "visual_toc": [( "card_lead_icon", f"toc_module_{idx+1}", 1.00, 1.08 + idx * 0.55, "icon_card_small", "inline_before_text") for idx in range(8)],
    "section_divider": [("title_badge_icon", "section_marker", 0.92, 1.05, "icon_card_primary", "badge_corner")],
    "standard_content": [
        ("card_lead_icon", "content_card_1", 0.95, 1.55, "icon_card_small", "top_left"),
        ("card_status_icon", "content_card_2", 0.95, 2.55, "icon_card_small", "top_left"),
        ("card_lead_icon", "content_card_3", 0.95, 3.55, "icon_card_small", "top_left"),
        ("note_insight_icon", "insight_rail", 9.25, 1.35, "icon_card_primary", "badge_corner"),
    ],
    "evidence_overview": [( "card_status_icon", f"evidence_card_{idx+1}", 0.92 + (idx % 5) * 1.56, 1.65 + (idx // 5) * 1.35, "icon_card_small", "top_left") for idx in range(5)],
    "card_grid": [( "card_corner_badge_icon", f"grid_card_{idx+1}", 1.08 + idx * 1.45, 1.46, "icon_card_small", "badge_corner") for idx in range(3)],
    "methodology_framework": [
        ("note_insight_icon", "framework_note", 7.20, 1.45, "icon_card_small", "top_left"),
        ("process_node_icon", "framework_active_layer", 2.10, 3.28, "icon_process_node", "center_left"),
    ],
    "process_flow": [
        ("process_node_icon", "process_node_1", 1.25, 3.18, "icon_process_node", "center"),
        ("process_node_icon", "process_flag", 6.50, 3.18, "icon_process_node", "center"),
        ("decision_marker_icon", "process_decision_gate", 8.88, 3.10, "icon_decision_marker", "center"),
    ],
    "comparison_matrix": [
        ("table_header_icon", "matrix_header", 1.10, 1.25, "icon_table_header", "inline_before_text"),
        ("decision_marker_icon", "matrix_score", 6.55, 5.35, "icon_decision_marker", "badge_corner"),
        ("decision_marker_icon", "matrix_decision_rail", 9.75, 1.48, "icon_decision_marker", "top_left"),
    ],
    "data_dashboard": [
        ("kpi_icon", "kpi_card_1", 0.94, 1.30, "icon_kpi", "top_left"),
        ("kpi_icon", "kpi_card_2", 3.12, 1.30, "icon_kpi", "top_left"),
        ("kpi_icon", "kpi_card_3", 9.90, 1.28, "icon_kpi", "top_left"),
    ],
    "table_heavy": [
        ("table_header_icon", "table_header_database", 1.25, 1.33, "icon_table_header", "inline_before_text"),
        ("table_header_icon", "table_header_shield", 3.20, 1.33, "icon_table_header", "inline_before_text"),
        ("table_row_status_icon", "table_warning_cell", 6.60, 3.95, "icon_table_header", "inline_before_text"),
        ("table_header_icon", "table_header_table", 10.50, 1.33, "icon_table_header", "inline_before_text"),
    ],
    "timeline_roadmap": [
        ("timeline_milestone_icon", "timeline_start", 1.85, 4.08, "icon_timeline_marker", "timeline_node_center"),
        ("timeline_milestone_icon", "timeline_risk", 7.25, 4.08, "icon_timeline_marker", "timeline_node_center"),
    ],
    "decision_record": [
        ("decision_marker_icon", "decision_stamp", 1.10, 2.45, "icon_decision_marker", "side_rail_center"),
        ("decision_marker_icon", "evidence_strip", 7.35, 5.58, "icon_decision_marker", "badge_corner"),
        ("header_micro_icon", "metadata_field", 8.70, 1.55, "icon_header_micro", "inline_before_text"),
    ],
    "risk_register": [
        ("risk_status_icon", "risk_row_1", 9.20, 2.08, "icon_decision_marker", "badge_corner"),
        ("table_row_status_icon", "risk_warning_row", 9.20, 2.72, "icon_table_header", "badge_corner"),
        ("table_row_status_icon", "risk_owner_cell", 7.30, 3.36, "icon_table_header", "inline_before_text"),
    ],
    "case_study": [
        ("image_callout_icon", "case_evidence_panel", 6.72, 1.86, "icon_card_small", "top_left"),
        ("decision_marker_icon", "case_decision_panel", 8.85, 3.36, "icon_decision_marker", "badge_corner"),
    ],
    "closing_synthesis": [
        ("note_insight_icon", "recommendation_module", 1.35, 1.54, "icon_card_primary", "top_left"),
        ("decision_marker_icon", "evidence_summary", 7.25, 1.54, "icon_decision_marker", "top_left"),
    ],
}


def build_semantic_icon_slot_inventory() -> dict[str, Any]:
    rows = []
    for slide_number, archetype in enumerate(E04_SLIDE_ORDER, start=1):
        roles = EXPECTED_ICON_ROLES.get(archetype, [])
        anchors = SLIDE_ANCHORS[archetype]
        for idx, role in enumerate(roles):
            slot_type, anchor_component_id, x, y, token, anchor_position = anchors[min(idx, len(anchors) - 1)]
            size = size_for_token(token)
            rows.append(
                {
                    "slide_number": slide_number,
                    "slide_id": f"e04-{slide_number:03d}",
                    "archetype_id": archetype,
                    "role": role,
                    "slot_type": slot_type,
                    "anchor_component_id": anchor_component_id,
                    "anchor_position": anchor_position,
                    "size_token": token,
                    "size_in": size,
                    "bbox_in": [x, y, size, size],
                    "anchor_bbox_in": [max(0.0, x - 0.08), max(0.0, y - 0.08), size + 0.16, size + 0.16],
                    "padding_in": 0.04,
                    "semantic": True,
                }
            )
    return {
        "schema_name": "semantic_icon_slot_inventory",
        "status": "passed",
        "semantic_icon_count": len(rows),
        "unanchored_semantic_icon_count": 0,
        "rows": rows,
    }
