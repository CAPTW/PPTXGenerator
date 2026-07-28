"""Semantic icon slot taxonomy for E04.1."""

from __future__ import annotations


SLOT_TAXONOMY: dict[str, dict[str, object]] = {
    "header_micro_icon": {"allowed_roles": ["document", "calendar", "user", "flag"], "required_component_anchor": "title_meta_bar", "size_token": "icon_header_micro", "semantic": True},
    "title_badge_icon": {"allowed_roles": ["flag", "recommendation", "decision_diamond"], "required_component_anchor": "title_badge", "size_token": "icon_card_primary", "semantic": True},
    "meta_bar_icon": {"allowed_roles": ["calendar", "user", "flag", "source"], "required_component_anchor": "meta_bar", "size_token": "icon_hero_meta", "semantic": True},
    "card_lead_icon": {"allowed_roles": ["database", "shield", "chart_bar", "note", "warning", "scale", "document", "book", "evidence_trace"], "required_component_anchor": "card_panel", "size_token": "icon_card_small", "semantic": True},
    "card_status_icon": {"allowed_roles": ["shield", "warning", "risk_status", "file_check"], "required_component_anchor": "card_panel", "size_token": "icon_card_small", "semantic": True},
    "card_corner_badge_icon": {"allowed_roles": ["chart_bar", "warning", "scale"], "required_component_anchor": "card_panel", "size_token": "icon_card_small", "semantic": True},
    "kpi_icon": {"allowed_roles": ["chart_bar", "database", "warning", "kpi"], "required_component_anchor": "kpi_card", "size_token": "icon_kpi", "semantic": True},
    "chart_marker_icon": {"allowed_roles": ["chart_bar", "pie_chart", "dashboard"], "required_component_anchor": "chart_region", "size_token": "icon_table_header", "semantic": True},
    "table_header_icon": {"allowed_roles": ["table", "database", "shield", "warning", "user"], "required_component_anchor": "table_header", "size_token": "icon_table_header", "semantic": True},
    "table_row_status_icon": {"allowed_roles": ["warning", "risk_status", "shield", "user"], "required_component_anchor": "table_row", "size_token": "icon_table_header", "semantic": True},
    "side_rail_icon": {"allowed_roles": ["network", "database", "book", "document"], "required_component_anchor": "side_rail", "size_token": "icon_side_rail", "semantic": True},
    "timeline_milestone_icon": {"allowed_roles": ["clock", "flag", "risk_status"], "required_component_anchor": "timeline_milestone", "size_token": "icon_timeline_marker", "semantic": True},
    "process_node_icon": {"allowed_roles": ["process_node", "flag", "decision_diamond"], "required_component_anchor": "process_node", "size_token": "icon_process_node", "semantic": True},
    "decision_marker_icon": {"allowed_roles": ["decision_diamond", "approval", "evidence_trace"], "required_component_anchor": "decision_panel", "size_token": "icon_decision_marker", "semantic": True},
    "risk_status_icon": {"allowed_roles": ["risk_status", "warning", "shield"], "required_component_anchor": "risk_register", "size_token": "icon_decision_marker", "semantic": True},
    "source_footer_icon": {"allowed_roles": ["source", "citation"], "required_component_anchor": "source_footer", "size_token": "icon_footer_source", "semantic": True},
    "citation_icon": {"allowed_roles": ["citation", "source"], "required_component_anchor": "citation_text", "size_token": "icon_footer_source", "semantic": True},
    "note_insight_icon": {"allowed_roles": ["note", "insight", "recommendation"], "required_component_anchor": "insight_panel", "size_token": "icon_card_small", "semantic": True},
    "image_callout_icon": {"allowed_roles": ["evidence_trace", "decision_diamond"], "required_component_anchor": "image_frame", "size_token": "icon_card_small", "semantic": True},
    "decorative_optional_icon": {"allowed_roles": [], "required_component_anchor": "decorative_region", "size_token": "icon_header_micro", "semantic": False},
    "qa_diagnostic_icon": {"allowed_roles": [], "required_component_anchor": "qa_overlay", "size_token": "icon_micro_qa", "semantic": False},
}


def build_semantic_icon_slot_taxonomy_v1() -> dict[str, object]:
    return {
        "schema_name": "semantic_icon_slot_taxonomy_v1",
        "status": "passed",
        "slot_types": SLOT_TAXONOMY,
        "slot_type_count": len(SLOT_TAXONOMY),
    }
