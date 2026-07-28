"""Reclassify E03.2.2 before complex icon vectorization."""

from __future__ import annotations

from typing import Any


DECISION = "E03_2_2_RECLASSIFIED_ICON_HYGIENE_PARTIAL_PASS_COMPLEX_VECTORIZATION_REQUIRED"


def reclassify_e03_2_2(previous_report: dict[str, Any] | None = None) -> dict[str, Any]:
    previous_report = previous_report or {}
    return {
        "schema_name": "e03_2_2_reclassification_report",
        "status": "passed",
        "decision": DECISION,
        "previous_decision": previous_report.get("decision"),
        "e03_2_2_hygiene_status": "PARTIAL_PASS",
        "e03_2_2_curated_v4_status": "PARTIAL_PASS",
        "e03_2_2_simple_icon_status": "PASS",
        "e03_2_2_complex_icon_status": "INSUFFICIENT",
        "e03_2_2_false_positive_gate_status": "TOO_PERMISSIVE",
        "e03_2_2_vision_trace_input_quality": "INSUFFICIENT_FOR_COMPLEX_ICONS",
        "e03_3_unlock_status": "REVOKED_PENDING_E03_2_3",
        "e04_status": "LOCKED",
        "broad_canva_parity_claimed": False,
    }
