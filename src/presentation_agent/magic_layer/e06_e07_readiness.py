"""E07 readiness gate for E06."""

from __future__ import annotations

from typing import Any


def build_e07_readiness_report(
    *,
    handoff: dict[str, Any],
    slide_matrix: dict[str, Any],
    baseline_manifest: dict[str, Any],
    risk_register: dict[str, Any],
    source_integrity: dict[str, Any],
    contract_policy: dict[str, Any],
    editability: dict[str, Any],
    icon_system: dict[str, Any],
    dense_readability: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "e04_2_handoff_passed": handoff.get("status") == "passed",
        "e06_product_review_passed": slide_matrix.get("status") == "passed",
        "baseline_candidate_package_exists": baseline_manifest.get("status") == "created",
        "critical_blockers_zero": risk_register.get("critical_blocker_count", 1) == 0,
        "high_product_risks_zero": risk_register.get("high_product_risk_count", 1) == 0,
        "average_score_min": float(slide_matrix.get("average_baseline_score", 0)) >= 4.35,
        "minimum_slide_score_min": float(slide_matrix.get("minimum_slide_score", 0)) >= 4.0,
        "source_citation_slot_binding_pass": source_integrity.get("status") == "passed",
        "contract_v2_pass": contract_policy.get("contract_v2_status") == "passed" or contract_policy.get("status") == "passed",
        "semantic_editability_pass": editability.get("status") == "passed",
        "semantic_raster_zero": contract_policy.get("semantic_raster_violation_count", 1) == 0,
        "full_slide_raster_zero": contract_policy.get("full_slide_raster_count", 1) == 0,
        "screenshot_slide_zero": contract_policy.get("screenshot_slide_count", 1) == 0,
        "icon_system_pass": icon_system.get("status") == "passed",
        "dense_slide_readability_pass": dense_readability.get("status") == "passed",
        "protected_artifacts_unchanged": protected_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e07_readiness_report",
        "status": "passed" if passed else "locked",
        "decision": "E07_READY_START_BASELINE_PROMOTION_REVIEW" if passed else "E07_LOCKED_PENDING_E04_3_OR_E06_PATCH",
        "e07_unlocked": passed,
        "checks": checks,
        "next_stage": "E07_BASELINE_PROMOTION_REVIEW" if passed else "E04.3_OR_E06_PATCH",
        "d08_status": "LOCKED",
        "c11_status": "LOCKED",
        "bulk_scaleout_status": "LOCKED",
        "broad_canva_parity_claimed": False,
    }


def decision_from_e07(e07: dict[str, Any], contract_policy: dict[str, Any], risk_register: dict[str, Any], dense: dict[str, Any], icon: dict[str, Any], rhythm: dict[str, Any]) -> str:
    if contract_policy.get("semantic_raster_violation_count", 0):
        return "E06_FAIL_SEMANTIC_RASTER_VIOLATION"
    if contract_policy.get("full_slide_raster_count", 0) or contract_policy.get("screenshot_slide_count", 0):
        return "E06_FAIL_SCREENSHOT_OR_FULL_SLIDE_RASTER"
    if e07.get("e07_unlocked"):
        return "E06_PASS_START_E07_BASELINE_PROMOTION_REVIEW"
    if risk_register.get("high_product_risk_count", 0) or risk_register.get("critical_blocker_count", 0):
        return "E06_PATCH_REQUIRED_START_E04_3_PRODUCT_POLISH"
    if dense.get("status") != "passed":
        return "E06_PATCH_REQUIRED_DENSE_SLIDE_READABILITY"
    if icon.get("status") != "passed":
        return "E06_PATCH_REQUIRED_ICON_SYSTEM"
    if rhythm.get("status") != "passed":
        return "E06_PATCH_REQUIRED_VISUAL_RHYTHM"
    return "E06_PATCH_REQUIRED_START_E04_3_PRODUCT_POLISH"

