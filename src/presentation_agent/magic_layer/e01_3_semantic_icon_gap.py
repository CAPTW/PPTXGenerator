"""Semantic icon gap analysis for E01.3."""

from __future__ import annotations

from typing import Any


REQUIRED_ICON_ROLES = [
    {"role_id": "checklist_plan_prepare", "component": "checklist", "preferred": ["clipboard", "checklist", "document-check"]},
    {"role_id": "valve_setup_secure", "component": "checklist", "preferred": ["valve", "pipeline"]},
    {"role_id": "gauge_execute_monitor", "component": "checklist", "preferred": ["gauge", "monitor"]},
    {"role_id": "shield_verify_confirm", "component": "checklist", "preferred": ["shield-check"]},
    {"role_id": "document_complete_record", "component": "checklist", "preferred": ["document", "file-check", "clipboard-list"]},
    {"role_id": "chevron_next", "component": "checklist", "preferred": ["chevron", "arrow-right"]},
    {"role_id": "warning_wear_ppe", "component": "bottom_action_bar", "preferred": ["warning", "alert"]},
    {"role_id": "hardhat_or_ppe", "component": "bottom_action_bar", "preferred": ["hardhat", "helmet", "ppe"]},
    {"role_id": "lock_zero_leak", "component": "bottom_action_bar", "preferred": ["lock"]},
    {"role_id": "droplet_or_spill_control", "component": "bottom_action_bar", "preferred": ["droplet", "spill"]},
    {"role_id": "shield_chemical_barrier", "component": "bottom_action_bar", "preferred": ["shield", "barrier", "chemical"]},
    {"role_id": "chat_communicate_confirm", "component": "bottom_action_bar", "preferred": ["chat", "message-check"]},
    {"role_id": "users_teamwork", "component": "bottom_action_bar", "preferred": ["users", "team"]},
    {"role_id": "cargo_control_room", "component": "thumbnail_callouts", "preferred": ["control-room", "monitor"]},
    {"role_id": "pump_or_equipment", "component": "thumbnail_callouts", "preferred": ["pump", "equipment"]},
    {"role_id": "gas_detection_or_respirator", "component": "thumbnail_callouts", "preferred": ["gas", "respirator", "sensor"]},
    {"role_id": "source_database", "component": "source_footer", "preferred": ["database"]},
    {"role_id": "footer_marker", "component": "source_footer", "preferred": ["marker", "line"]},
]


def build_semantic_icon_role_requirements_e01_3() -> dict[str, Any]:
    return {
        "schema_name": "semantic_icon_role_requirements_e01_3",
        "required_role_count": len(REQUIRED_ICON_ROLES),
        "roles": REQUIRED_ICON_ROLES,
        "generic_icon_allowed_for_semantic_roles": False,
        "raster_icon_fallback_allowed": False,
        "canva_parity_claimed": False,
    }


def build_missing_semantic_icon_gap_report(match_report: dict[str, Any]) -> dict[str, Any]:
    unresolved = [item for item in match_report["matches"] if item["classification"] == "UNRESOLVED_BLOCKING"]
    generated = [item for item in match_report["matches"] if item["classification"] == "GENERATED_PROCEDURAL_REQUIRED"]
    return {
        "schema_name": "missing_semantic_icon_gap_report",
        "status": "passed" if not unresolved else "failed",
        "required_role_count": len(match_report["matches"]),
        "generated_procedural_required_count": len(generated),
        "unresolved_blocking_count": len(unresolved),
        "matches": match_report["matches"],
        "canva_parity_claimed": False,
    }

