"""Patch planning for E03.1 archetypes."""

from __future__ import annotations

from typing import Any

from .e03_16_orchestrator import CORE_ARCHETYPES, EXPANSION_ARCHETYPES


PATCH_ACTIONS = {
    "section_divider": ["restore_section_marker", "strengthen_diagonal_slab", "reinforce_transition_identity"],
    "visual_toc": ["restore_navigation_sequence", "add_active_marker", "strengthen_side_meta_panel"],
    "evidence_overview": ["increase_evidence_card_trace_density", "restore_confidence_markers", "strengthen_summary_strip"],
    "card_grid": ["restore_8_card_modularity", "add_category_header_chrome", "strengthen_insight_strip"],
    "methodology_framework": ["restore_layered_framework_rows", "add_connector_rail", "mark_active_layer"],
    "process_flow": ["increase_process_node_density", "restore_decision_gate", "add_directional_connectors"],
    "comparison_matrix": ["restore_matrix_density", "add_score_marker_rhythm", "strengthen_decision_rail"],
    "timeline_roadmap": ["restore_phase_axis", "add_milestones", "restore_risk_mission_rows"],
    "decision_record": ["restore_decision_stamp_sidebar", "add_metadata_fields", "restore_evidence_strip"],
    "risk_register": ["restore_dense_register_grid", "add_severity_status_markers", "strengthen_side_meta_rail"],
    "case_study": ["restore_bounded_case_image", "add_context_evidence_result_modules", "strengthen_lesson_strip"],
    "closing_synthesis": ["restore_recommendation_next_action_evidence_modules", "strengthen_final_takeaway", "avoid_generic_three_cards"],
}


def build_patch_plan(archetype_id: str, gap_report: dict[str, Any]) -> dict[str, Any]:
    if archetype_id in CORE_ARCHETYPES:
        actions: list[str] = []
        policy = "preserve_existing_e03_core_candidate"
    else:
        actions = PATCH_ACTIONS[archetype_id]
        policy = "patch_expansion_reference_fidelity"
    return {
        "schema_name": "e03_1_patch_plan",
        "status": "planned",
        "archetype_id": archetype_id,
        "patch_required": archetype_id in EXPANSION_ARCHETYPES,
        "priority": "core_stability" if archetype_id in CORE_ARCHETYPES else "expansion_fidelity_patch",
        "actions": actions,
        "input_defects": gap_report.get("defects", []),
        "policy": policy,
        "semantic_editability_must_be_preserved": True,
        "full_slide_raster_forbidden": True,
        "semantic_raster_forbidden": True,
    }


def build_patch_queue(plans: dict[str, dict[str, Any]], pass_after_patch: bool) -> dict[str, Any]:
    items = []
    if not pass_after_patch:
        for archetype_id in EXPANSION_ARCHETYPES:
            items.append({"archetype_id": archetype_id, "actions": plans[archetype_id]["actions"], "severity": "high"})
    return {"schema_name": "e03_1_archetype_patch_queue", "status": "empty" if pass_after_patch else "open", "items": items}
