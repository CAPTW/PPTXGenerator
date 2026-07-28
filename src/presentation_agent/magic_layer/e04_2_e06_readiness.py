"""E06 readiness after E04.2 product polish."""

from __future__ import annotations

from typing import Any


def build_e04_2_e06_readiness_report(
    *,
    product_scorecard: dict[str, Any],
    source_regression: dict[str, Any],
    citation_regression: dict[str, Any],
    slot_regression: dict[str, Any],
    contract: dict[str, Any],
    raster: dict[str, Any],
    text: dict[str, Any],
    icon: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "critical_blockers_zero": product_scorecard.get("critical_blocker_count", 1) == 0,
        "high_product_risks_zero": product_scorecard.get("high_product_risk_count", 1) == 0,
        "average_product_score_min": float(product_scorecard.get("average_product_score", 0)) >= 4.35,
        "minimum_slide_score_min": float(product_scorecard.get("minimum_slide_score", 0)) >= 4.0,
        "target_slide_scores_min": product_scorecard.get("slide_09_score", 0) >= 4.0 and product_scorecard.get("slide_11_score", 0) >= 4.0 and product_scorecard.get("slide_14_score", 0) >= 4.0,
        "text_readability_passed": text.get("status") == "passed",
        "source_citation_slot_regression_zero": source_regression.get("source_binding_regression_count", 1) == 0
        and citation_regression.get("citation_binding_regression_count", 1) == 0
        and slot_regression.get("slot_binding_regression_count", 1) == 0,
        "contract_v2_passed": contract.get("status") == "passed",
        "semantic_raster_zero": raster.get("semantic_raster_violation_count", 1) == 0,
        "full_slide_raster_zero": raster.get("full_slide_raster_count", 1) == 0,
        "screenshot_slide_zero": raster.get("screenshot_slide_count", 1) == 0,
        "text_overflow_clipping_zero": text.get("text_overflow_count", 1) == 0 and text.get("text_clipping_count", 1) == 0,
        "icons_visible_and_anchored": icon.get("invisible_icon_count", 1) == 0 and icon.get("unanchored_semantic_icon_count", 1) == 0,
        "protected_artifacts_unchanged": protected_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e06_readiness_report",
        "status": "passed" if passed else "locked",
        "decision": "E06_READY_START_CONTROLLED_PRODUCT_BASELINE_REVIEW" if passed else "E06_LOCKED_PENDING_E04_2_1_DENSE_READABILITY_PATCH",
        "e06_unlocked": passed,
        "checks": checks,
        "next_stage": "E06_CONTROLLED_PRODUCT_BASELINE_REVIEW" if passed else "E04.2.1_DENSE_READABILITY_PATCH",
        "d08_status": "LOCKED",
        "c11_status": "LOCKED",
        "bulk_scaleout_status": "LOCKED",
        "broad_canva_parity_claimed": False,
    }


def decision_from_e06(e06: dict[str, Any], source: dict[str, Any], citation: dict[str, Any], slot: dict[str, Any], raster: dict[str, Any], text: dict[str, Any], table_density: dict[str, Any], source_footer: dict[str, Any], scorecard: dict[str, Any]) -> str:
    if source.get("source_binding_regression_count", 0):
        return "E04_2_FAIL_SOURCE_BINDING_REGRESSION"
    if citation.get("citation_binding_regression_count", 0):
        return "E04_2_FAIL_CITATION_BINDING_REGRESSION"
    if slot.get("slot_binding_regression_count", 0):
        return "E04_2_FAIL_SLOT_BINDING_REGRESSION"
    if raster.get("semantic_raster_violation_count", 0):
        return "E04_2_FAIL_SEMANTIC_RASTER_VIOLATION"
    if raster.get("full_slide_raster_count", 0) or raster.get("screenshot_slide_count", 0):
        return "E04_2_FAIL_SCREENSHOT_OR_FULL_SLIDE_RASTER"
    if e06.get("e06_unlocked"):
        return "E04_2_PASS_START_E06_CONTROLLED_PRODUCT_BASELINE_REVIEW"
    if text.get("status") != "passed":
        return "E04_2_PATCH_TEXT_CAPACITY_REQUIRED"
    if table_density.get("status") != "passed":
        return "E04_2_PATCH_DENSE_TABLE_READABILITY_REQUIRED"
    if source_footer.get("status") != "passed":
        return "E04_2_PATCH_SOURCE_FOOTER_READABILITY_REQUIRED"
    return "E04_2_PATCH_VISUAL_HIERARCHY_REQUIRED"

