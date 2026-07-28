"""E06.4 reclassification of E06.3."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e03_16_orchestrator import read_json


EXPECTED_E06_3_DECISION = "E06_3_PASS_START_E07_BASELINE_PROMOTION_REVIEW_WITH_IMPROVED_CONTRACT_CANDIDATE"


def build_e06_3_reclassification_report(e06_3_root: Path) -> dict[str, Any]:
    report = read_json(e06_3_root / "e06_3_contract_driven_product_improvement_report.json", default={})
    decision = report.get("final_decision") or report.get("decision")
    avg_delta = float(report.get("average_score_delta", 0.0))
    selected_exists = (e06_3_root / "selected_candidate" / "harness_v3_e06_3_contract_driven_improved_baseline_candidate.pptx").exists()
    pass_structural = decision == EXPECTED_E06_3_DECISION and selected_exists
    return {
        "schema_name": "e06_3_reclassification_report",
        "status": "passed" if pass_structural else "failed",
        "original_decision": decision,
        "e06_3_variant_generation_status": "PASS" if pass_structural else "MISSING_OR_FAIL",
        "e06_3_contract_compile_status": "PASS" if pass_structural else "MISSING_OR_FAIL",
        "e06_3_binding_preservation_status": "PASS" if int(report.get("source_citation_slot_regression_count", 1)) == 0 else "FAIL",
        "e06_3_product_score_delta": "TOO_SMALL" if avg_delta < 0.03 else "SUFFICIENT",
        "e06_3_human_visual_improvement_status": "NOT_PROVEN",
        "e06_3_selected_candidate_status": "EXPERIMENTAL_ONLY",
        "e07_unlock_status": "REVOKED_PENDING_E06_4",
        "broad_canva_parity_claimed": False,
        "decision": "E06_3_RECLASSIFIED_CONTRACT_VARIANT_EXPERIMENT_PASS_HUMAN_GUIDED_TUNING_REQUIRED",
    }
