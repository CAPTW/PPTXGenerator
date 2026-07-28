from __future__ import annotations

from typing import Any


REQUIRED_PREFIXES = {
    "P03": "P03_PASS",
    "C04": "C04_PASS",
    "P04": "P04_PASS",
    "P05": "P05_PASS",
    "P06": "P06_PASS",
    "C05": "C05_PASS",
}


def decide_recovery_validation_bridge(evidence: dict[str, dict[str, Any]], *, bridge_blocking_gap_count: int) -> dict[str, Any]:
    missing_or_failed = [
        stage
        for stage, prefix in REQUIRED_PREFIXES.items()
        if not str(evidence.get(stage, {}).get("decision", "")).startswith(prefix)
    ]
    ready = not missing_or_failed and bridge_blocking_gap_count == 0
    decision = "BRIDGE_READY_WITH_LIMITATIONS_FOR_RV00" if ready else "BRIDGE_NOT_READY_PATCH_REQUIRED"
    return {
        "schema": "recovery_validation_bridge_decision.v1",
        "decision": decision,
        "missing_or_failed_stages": missing_or_failed,
        "bridge_blocking_gap_count": bridge_blocking_gap_count,
        "rv00_objective_lock_allowed": ready,
        "e03_direct_rerun_allowed": False,
        "product_pass": False,
    }


def build_e03_reopen_prerequisites() -> dict[str, Any]:
    return {
        "schema": "e03_reopen_prerequisite_report.v1",
        "decision": "E03_CAN_BE_PLANNED_VIA_RV00",
        "direct_e03_rerun_allowed": False,
        "required_before_actual_rerun": [
            "explicit recovery validation objective lock",
            "active run folder selection",
            "E03 expansion reference registry",
            "minimum 8 valid expansion references",
            "preferably 12 valid expansion references",
            "per-reference dimension/source/semantic/legibility validation",
        ],
        "product_pass": False,
    }


def build_e03_reference_gap_report() -> dict[str, Any]:
    return {
        "schema": "e03_reference_readiness_gap_report.v1",
        "decision": "E03_DIRECT_RERUN_BLOCKED_UNTIL_REFERENCE_READINESS",
        "gaps": [
            "E03 expansion references are not validated in P07",
            "generated-flood/contact-sheet/render references remain forbidden",
            "12-16 archetype pack evidence is absent in rebuilt Pipeline v2",
        ],
        "product_pass": False,
    }
