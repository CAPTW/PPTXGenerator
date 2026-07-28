from __future__ import annotations

from typing import Any


def build_e03_reopen_policy() -> dict[str, Any]:
    return {
        "schema": "e03_reopen_policy.v1",
        "e03_opened_by_rv00": False,
        "direct_e03_rerun_allowed": False,
        "e03_planning_allowed_after_rv00": True,
        "e03_execution_requires": ["RV01_REFERENCE_READINESS_PASS", "active_run_004_input_registry"],
        "generated_flood_allowed": False,
        "render_or_contact_sheet_references_allowed": False,
        "canonical_artifacts_allowed": False,
        "e04_d08_unlock_by_rv00": False,
        "product_pass": False,
    }


def build_e03_direct_rerun_block_report() -> dict[str, Any]:
    return {
        "schema": "e03_direct_rerun_block_report.v1",
        "decision": "DIRECT_E03_RERUN_BLOCKED_REFERENCE_READINESS_REQUIRED",
        "direct_e03_rerun_allowed": False,
        "rv01_reference_revalidation_required": True,
        "product_pass": False,
    }
