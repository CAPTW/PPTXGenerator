"""E05 readiness decision for E04."""

from __future__ import annotations

from typing import Any


def build_e05_readiness_report(
    *,
    deck_exists: bool,
    rendered_count: int,
    slot_ledger: dict[str, Any],
    source_ledger: dict[str, Any],
    citation_ledger: dict[str, Any],
    contract: dict[str, Any],
    icon_visibility: dict[str, Any],
    raster_policy: dict[str, Any],
    text_report: dict[str, Any],
    unknown_layer: dict[str, Any],
    visual_fidelity: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "deck_exists": deck_exists,
        "rendered_16_of_16": rendered_count == 16,
        "slot_binding_passed": slot_ledger.get("status") == "passed",
        "source_binding_passed": source_ledger.get("status") == "passed",
        "citation_binding_passed": citation_ledger.get("status") == "passed",
        "contract_v2_passed": contract.get("status") == "passed",
        "icon_v7_1_visibility_passed": icon_visibility.get("status") == "passed",
        "semantic_raster_zero": int(raster_policy.get("semantic_raster_violation_count", 0)) == 0,
        "full_slide_raster_zero": int(raster_policy.get("full_slide_raster_count", 0)) == 0,
        "screenshot_slide_zero": int(raster_policy.get("screenshot_slide_count", 0)) == 0,
        "text_overflow_clipping_zero": int(text_report.get("text_overflow_count", 0)) == 0 and int(text_report.get("text_clipping_count", 0)) == 0,
        "unknown_content_bearing_zero": int(unknown_layer.get("unknown_content_bearing_count", 0)) == 0,
        "visual_fidelity_passed": visual_fidelity.get("status") == "passed",
        "protected_artifacts_unchanged": protected_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e05_readiness_report",
        "status": "passed" if passed else "blocked",
        "decision": "E05_SOURCE_BOUND_PRODUCT_REVIEW_AND_PATCH_QUEUE" if passed else "E05_LOCKED_PENDING_E04_PATCH",
        "e05_unlocked": passed,
        "checks": checks,
        "next_stage": "E05_SOURCE_BOUND_PRODUCT_REVIEW_AND_PATCH_QUEUE" if passed else "E04_PATCH",
        "d08_status": "LOCKED",
        "c11_status": "FROZEN",
        "bulk_scaleout_status": "LOCKED",
        "broad_canva_parity_claimed": False,
    }
