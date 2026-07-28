"""E06.3 reclassification helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e03_16_orchestrator import read_json


EXPECTED_E06_2_1_DECISION = "E06_2_1_PASS_START_E07_BASELINE_PROMOTION_REVIEW_WITH_STYLE_CONTENT_CONTRACT"


def build_e06_2_1_reclassification_report(e06_2_1_root: Path) -> dict[str, Any]:
    report = read_json(e06_2_1_root / "e06_2_1_contract_style_content_fidelity_report.json", default={})
    decision = report.get("final_decision") or report.get("decision")
    passed = decision == EXPECTED_E06_2_1_DECISION
    return {
        "schema_name": "e06_2_1_reclassification_report",
        "status": "passed" if passed else "failed",
        "original_decision": decision,
        "e06_2_1_contract_first_fidelity_status": "PASS" if passed else "MISSING_OR_FAIL",
        "e06_2_1_text_content_preservation_status": "PASS" if passed else "MISSING_OR_FAIL",
        "e06_2_1_style_content_preservation_status": "PASS" if passed else "MISSING_OR_FAIL",
        "e06_2_1_product_quality_improvement_status": "NOT_PROVEN",
        "e06_2_1_baseline_restoration_status": "PASS" if passed else "MISSING_OR_FAIL",
        "e07_unlock_status": "REVOKED_PENDING_E06_3",
        "broad_canva_parity_claimed": False,
        "decision": "E06_2_1_RECLASSIFIED_CONTRACT_RECOMPILE_RESTORATION_PASS_PRODUCT_IMPROVEMENT_REQUIRED",
    }
