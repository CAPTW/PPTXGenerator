"""Reclassify E03.2.3 before human-reviewed complex icon authoring."""

from __future__ import annotations

from typing import Any


DECISION = "E03_2_3_RECLASSIFIED_STRUCTURAL_TRACE_PIPELINE_PASS_COMPLEX_ICON_FIDELITY_PATCH_REQUIRED"


def reclassify_e03_2_3(previous_report: dict[str, Any] | None = None) -> dict[str, Any]:
    previous_report = previous_report or {}
    return {
        "schema_name": "e03_2_3_reclassification_report",
        "status": "passed",
        "decision": DECISION,
        "previous_decision": previous_report.get("decision"),
        "e03_2_3_hygiene_status": "IMPROVED",
        "e03_2_3_trace_pipeline_status": "STRUCTURAL_PASS",
        "e03_2_3_local_trace_candidate_status": "PARTIAL",
        "e03_2_3_complex_icon_fidelity_status": "FAIL_OR_NOT_PROVEN",
        "e03_2_3_human_review_status": "TOO_PERMISSIVE",
        "e03_2_3_generic_placeholder_risk": "HIGH",
        "e03_3_unlock_status": "REVOKED_PENDING_E03_2_4",
        "e04_status": "LOCKED",
        "broad_canva_parity_claimed": False,
    }
