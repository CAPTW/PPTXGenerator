"""E05 readiness after E04.1 icon micro-placement."""

from __future__ import annotations

from typing import Any


def build_e04_1_e05_readiness_report(
    *,
    deck_exists: bool,
    rendered_count: int,
    micro_ledger: dict[str, Any],
    size_ledger: dict[str, Any],
    visibility: dict[str, Any],
    contrast: dict[str, Any],
    collision: dict[str, Any],
    diagnostic_after_count: int,
    binding_regression: dict[str, Any],
    contract: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "deck_exists": deck_exists,
        "rendered_16_of_16": rendered_count == 16,
        "semantic_icon_count_excludes_qa": micro_ledger.get("final_semantic_icon_count") == 51,
        "all_semantic_icons_anchored": micro_ledger.get("unanchored_semantic_icon_count") == 0,
        "no_diagnostic_top_right_cluster": diagnostic_after_count == 0,
        "size_token_compliance": size_ledger.get("status") == "passed",
        "icon_visibility_passed": visibility.get("status") == "passed",
        "icon_contrast_passed": contrast.get("status") == "passed",
        "icon_text_collision_zero": collision.get("icon_text_collision_count") == 0,
        "source_citation_slot_regression_zero": binding_regression.get("status") == "passed",
        "contract_v2_passed": contract.get("status") == "passed",
        "semantic_raster_zero": micro_ledger.get("semantic_raster_icon_count") == 0,
        "protected_artifacts_unchanged": protected_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e05_revised_readiness_report",
        "status": "passed" if passed else "blocked",
        "decision": "E05_READY_START_SOURCE_BOUND_PRODUCT_REVIEW" if passed else "E05_LOCKED_PENDING_E04_1_PATCH",
        "e05_unlocked": passed,
        "checks": checks,
        "d08_status": "LOCKED",
        "c11_status": "LOCKED",
        "broad_canva_parity_claimed": False,
    }
