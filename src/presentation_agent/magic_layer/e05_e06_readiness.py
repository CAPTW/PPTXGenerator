"""E06 readiness decision after E05 product review."""

from __future__ import annotations

from typing import Any


def build_e06_readiness_report(
    *,
    handoff: dict[str, Any],
    scorecard: dict[str, Any],
    patch_queue: dict[str, Any],
    source_review: dict[str, Any],
    contract_status: str,
    raster_review: dict[str, Any],
    text_review: dict[str, Any],
    icon_review: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "e04_1_handoff_passed": handoff.get("status") == "passed",
        "no_critical_blockers": patch_queue.get("critical_blocker_count", 0) == 0,
        "no_high_product_risks": patch_queue.get("high_product_risk_count", 0) == 0,
        "source_citation_slot_binding_pass": source_review.get("missing_source_binding_count", 1) == 0
        and source_review.get("missing_citation_binding_count", 1) == 0
        and source_review.get("missing_slot_binding_count", 1) == 0,
        "contract_v2_pass": contract_status == "passed",
        "semantic_raster_zero": raster_review.get("semantic_raster_violation_count", 1) == 0,
        "full_slide_raster_zero": raster_review.get("full_slide_raster_count", 1) == 0,
        "screenshot_slide_zero": raster_review.get("screenshot_slide_count", 1) == 0,
        "text_overflow_clipping_zero": text_review.get("text_overflow_count", 1) == 0 and text_review.get("text_clipping_count", 1) == 0,
        "icons_visible_and_anchored": icon_review.get("invisible_icon_count", 1) == 0 and icon_review.get("unanchored_semantic_icon_count", 1) == 0,
        "average_score_at_least_4": float(scorecard.get("average_product_score", 0.0)) >= 4.0,
        "minimum_slide_score_at_least_3_5": float(scorecard.get("minimum_slide_score", 0.0)) >= 3.5,
        "protected_artifacts_unchanged": protected_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e06_readiness_report",
        "status": "passed" if passed else "locked",
        "decision": "E06_READY_START_CONTROLLED_PRODUCT_BASELINE_REVIEW" if passed else "E06_LOCKED_PENDING_E04_2_PRODUCT_POLISH",
        "e06_unlocked": passed,
        "checks": checks,
        "next_stage": "E06_CONTROLLED_PRODUCT_BASELINE_REVIEW" if passed else "E04.2_SOURCE_BOUND_PRODUCT_POLISH",
        "d08_status": "LOCKED",
        "c11_status": "LOCKED",
        "bulk_scaleout_status": "LOCKED",
        "broad_canva_parity_claimed": False,
    }


def decision_from_e06(e06: dict[str, Any], patch_queue: dict[str, Any], source_review: dict[str, Any], raster_review: dict[str, Any]) -> str:
    if source_review.get("status") == "failed":
        return "E05_FAIL_SOURCE_BINDING_REGRESSION"
    if raster_review.get("semantic_raster_violation_count", 0):
        return "E05_FAIL_SEMANTIC_RASTER_VIOLATION"
    if raster_review.get("full_slide_raster_count", 0) or raster_review.get("screenshot_slide_count", 0):
        return "E05_FAIL_SCREENSHOT_OR_FULL_SLIDE_RASTER"
    if e06.get("e06_unlocked"):
        return "E05_PASS_START_E06_CONTROLLED_PRODUCT_BASELINE_REVIEW"
    return "E05_PATCH_REQUIRED_START_E04_2_SOURCE_BOUND_PRODUCT_POLISH"

