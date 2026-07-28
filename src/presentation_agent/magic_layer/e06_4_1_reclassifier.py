"""Reclassify E06.4 for the E06.4.1 human acceptance gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e03_16_orchestrator import read_json


EXPECTED_E06_4_DECISION = "E06_4_PASS_START_E07_BASELINE_PROMOTION_REVIEW_WITH_HUMAN_TUNED_CONTRACT"


def build_e06_4_reclassification_report(e06_4_root: Path) -> dict[str, Any]:
    report = read_json(e06_4_root / "e06_4_human_guided_contract_tuning_report.json", default={})
    decision = report.get("final_decision") or report.get("decision")
    structural_pass = decision == EXPECTED_E06_4_DECISION
    binding_pass = int(report.get("source_citation_slot_regression_count", 1)) == 0
    return {
        "schema_name": "e06_4_reclassification_report",
        "status": "passed" if structural_pass and binding_pass else "failed",
        "original_decision": decision,
        "e06_4_contract_tuning_mechanism_status": "PASS" if structural_pass else "MISSING_OR_FAIL",
        "e06_4_binding_preservation_status": "PASS" if binding_pass else "FAIL",
        "e06_4_semantic_editability_status": "PASS" if report.get("semantic_editability_verdict") == "passed" else "UNKNOWN_OR_FAIL",
        "e06_4_visual_improvement_status": "NOT_PROVEN",
        "e06_4_human_acceptance_status": "REQUIRED",
        "e07_unlock_status": "REVOKED_PENDING_E06_4_1",
        "broad_canva_parity_claimed": False,
        "decision": "E06_4_RECLASSIFIED_CONTRACT_TUNING_PASS_HUMAN_VISUAL_ACCEPTANCE_REQUIRED",
    }
