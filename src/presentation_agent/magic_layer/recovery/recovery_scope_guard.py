from __future__ import annotations

from typing import Any


def build_recovery_validation_scope_lock() -> dict[str, Any]:
    return {
        "schema": "recovery_validation_scope_lock.v1",
        "mode": "RECOVERY_VALIDATION_PLANNING_LOCK",
        "status": "RECOVERY_VALIDATION_PLANNING_LOCKED",
        "execution_status": "RECOVERY_VALIDATION_EXECUTION_NOT_STARTED",
        "e03_direct_rerun_status": "E03_DIRECT_RERUN_BLOCKED",
        "e03_execution_started": False,
        "product_pass": False,
    }


def build_allowed_forbidden_actions_policy() -> dict[str, Any]:
    return {
        "schema": "rv00_allowed_forbidden_actions_policy.v1",
        "allowed_actions": ["read_existing_evidence", "create_run_004_scaffold", "create_reference_registry_template", "create_planning_reports", "safe_tests", "protect_check"],
        "forbidden_actions": ["run_E03", "run_E03A", "generate_references", "generate_pptx", "render_pptx", "create_template_pack", "create_source_bound_deck", "E04", "D08", "C11", "bulk", "canonical_promotion"],
        "product_pass": False,
    }


def build_e04_d08_scaleout_block_report() -> dict[str, Any]:
    return {
        "schema": "e04_d08_scaleout_block_report.v1",
        "e04_allowed": False,
        "d08_allowed": False,
        "c11_bulk_allowed": False,
        "reason": "E04 remains blocked until E03 recovery validation passes; D08/C11/bulk remain blocked until E04 passes.",
        "product_pass": False,
    }


def build_canonical_promotion_block_report() -> dict[str, Any]:
    return {
        "schema": "canonical_promotion_block_report.v1",
        "canonical_promotion_allowed": False,
        "golden_template_masters_update_allowed": False,
        "final_deck_large_premium_update_allowed": False,
        "rv00_modifies_canonical_artifacts": False,
        "product_pass": False,
    }
