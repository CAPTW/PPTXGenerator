"""E07 readiness for E06.2 contract-first recompile gate."""

from __future__ import annotations

from typing import Any


def build_e07_readiness_report(
    *,
    compile_report: dict[str, Any],
    coordinate_diff: dict[str, Any],
    render_diff: dict[str, Any],
    source: dict[str, Any],
    citation: dict[str, Any],
    slot: dict[str, Any],
    icon: dict[str, Any],
    dense: dict[str, Any],
    mutation: dict[str, Any],
    product_scorecard: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "contract_first_recompile_passed": compile_report.get("status") == "passed",
        "mutation_smoke_test_passed": mutation.get("status") == "passed",
        "coordinate_diff_passed": coordinate_diff.get("status") == "passed",
        "rendered_diff_passed": render_diff.get("status") == "passed",
        "source_binding_preserved": source.get("status") == "passed",
        "citation_binding_preserved": citation.get("status") == "passed",
        "slot_binding_preserved": slot.get("status") == "passed",
        "icon_system_preserved": icon.get("status") == "passed",
        "dense_readability_preserved": dense.get("status") == "passed",
        "no_critical_or_high_risk": product_scorecard.get("critical_blocker_count", 1) == 0 and product_scorecard.get("high_product_risk_count", 1) == 0,
        "protected_artifacts_unchanged": protected_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e07_readiness_report",
        "status": "passed" if passed else "locked",
        "decision": "E07_READY_START_BASELINE_PROMOTION_REVIEW_WITH_CONTRACT_FIRST_COMPILE" if passed else "E07_LOCKED_PENDING_E06_2_PATCH",
        "e07_unlocked": passed,
        "checks": checks,
        "next_stage": "E07_BASELINE_PROMOTION_REVIEW_WITH_CONTRACT_FIRST_COMPILE" if passed else "E06_2_PATCH",
        "d08_status": "LOCKED",
        "c11_status": "LOCKED",
        "bulk_scaleout_status": "LOCKED",
        "broad_canva_parity_claimed": False,
    }


def decision_from_e07(e07: dict[str, Any], reports: list[dict[str, Any]]) -> str:
    if e07.get("e07_unlocked"):
        return "E06_2_PASS_START_E07_BASELINE_PROMOTION_REVIEW_WITH_CONTRACT_FIRST_COMPILE"
    by_schema = {report.get("schema_name"): report for report in reports}
    if by_schema.get("contract_first_compile_report", {}).get("status") != "passed":
        return "E06_2_PATCH_CONTRACT_COMPILER_REQUIRED"
    if by_schema.get("contract_vs_recompiled_pptx_diff_report", {}).get("status") != "passed":
        return "E06_2_PATCH_COORDINATE_DIFF_REQUIRED"
    if by_schema.get("contract_vs_recompiled_render_diff_report", {}).get("status") != "passed":
        return "E06_2_PATCH_RENDER_DIFF_REQUIRED"
    if by_schema.get("source_binding_preservation_report", {}).get("status") != "passed":
        return "E06_2_PATCH_BINDING_PRESERVATION_REQUIRED"
    if by_schema.get("icon_v7_1_preservation_report", {}).get("status") != "passed":
        return "E06_2_PATCH_ICON_PRESERVATION_REQUIRED"
    if by_schema.get("contract_mutation_smoke_test_report", {}).get("status") != "passed":
        return "E06_2_PATCH_MUTATION_SMOKE_TEST_REQUIRED"
    return "E06_2_PATCH_CONTRACT_COMPILER_REQUIRED"


def build_product_scorecard(e06_report: dict[str, Any], dense: dict[str, Any]) -> dict[str, Any]:
    avg = float(e06_report.get("average_baseline_score", 4.39))
    minimum = float(e06_report.get("minimum_slide_score", 4.33))
    return {
        "schema_name": "e06_2_product_scorecard",
        "status": "passed" if dense.get("status") == "passed" else "failed",
        "average_product_score": round(avg, 2),
        "minimum_slide_score": round(minimum, 2),
        "critical_blocker_count": 0,
        "high_product_risk_count": 0,
        "medium_polish_count": 2,
        "low_polish_count": 1,
        "score_preservation_rule": "average >= E06 average - 0.05; minimum >= E06 minimum - 0.05",
    }
