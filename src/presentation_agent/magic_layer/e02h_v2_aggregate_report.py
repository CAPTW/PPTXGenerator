"""Aggregate reporting and final decision helpers for E02H-V2."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_e02h_v2_final_decision(
    *,
    aggregate_status: str,
    protected_ok: bool,
    failure_regression_closed: bool,
) -> dict[str, Any]:
    if not protected_ok:
        decision = "E02H_V2_FAIL_PROTECTED_ARTIFACTS"
        status = "failed"
        reason = "Protected canonical artifact verification failed."
    elif aggregate_status == "passed" and failure_regression_closed:
        decision = "E02H_V2_PASS_READY_FOR_E03H_V2_REFERENCE_PACK"
        status = "passed"
        reason = "All holdout cases passed without baseline shortcut or semantic editability regressions."
    else:
        decision = "E02H_V2_FAIL_BASELINE_SHORTCUT_REMAINS"
        status = "patch_required"
        reason = "Holdout generalization gate detected a remaining E01H-V2 failure mode."
    return {
        "schema_name": "e02h_v2_final_decision",
        "status": status,
        "decision": decision,
        "reason": reason,
        "e03h_v2_unlocked": decision == "E02H_V2_PASS_READY_FOR_E03H_V2_REFERENCE_PACK",
        "e03h_v2_started": False,
        "e05_unlocked": False,
        "e05_started": False,
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "canva_parity_claimed": False,
    }


def build_e02h_v2_manifest(final: dict[str, Any], output_folder: str, case_count: int) -> dict[str, Any]:
    return {
        "schema_name": "e02h_v2_manifest",
        "status": final["status"],
        "decision": final["decision"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_folder": output_folder,
        "case_count": case_count,
        "e03h_v2_unlocked": final["e03h_v2_unlocked"],
        "e05_unlocked": False,
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "canva_parity_claimed": False,
    }


def build_readiness_reports(final: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    e03_ready = final["decision"] == "E02H_V2_PASS_READY_FOR_E03H_V2_REFERENCE_PACK"
    e03 = {
        "schema_name": "e03h_v2_readiness_report",
        "status": "ready" if e03_ready else "locked",
        "e03h_v2_unlocked": e03_ready,
        "e03h_v2_started": False,
        "reason": "E02H-V2 holdout generalization passed." if e03_ready else "E02H-V2 holdout generalization did not pass.",
        "e05_unlocked": False,
        "canva_parity_claimed": False,
    }
    e05 = {
        "schema_name": "e05_readiness_after_e02h_v2",
        "status": "locked",
        "e05_unlocked": False,
        "e05_started": False,
        "reason": "E02H-V2 may not unlock E05; E05 remains locked.",
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "canva_parity_claimed": False,
    }
    return e03, e05
