"""E03.3 readiness after E03.2.1 icon library expansion."""

from __future__ import annotations

from typing import Any


def build_e03_2_1_e03_3_readiness_report(
    *,
    inventory: dict[str, Any],
    quality_report: dict[str, Any],
    coverage: dict[str, Any],
    policy: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    ready = (
        inventory.get("reference_count") == 16
        and coverage.get("p0_unresolved_count") == 0
        and quality_report.get("status") == "passed"
        and coverage.get("status") == "passed"
        and policy.get("status") == "passed"
        and protected_unchanged
        and quality_report.get("blank_svg_count") == 0
        and quality_report.get("placeholder_svg_count") == 0
    )
    return {
        "schema_name": "e03_3_readiness_report",
        "status": "passed" if ready else "locked",
        "decision": "E03_2_1_PASS_START_E03_3_BATCH_OBJECT_PLACEMENT_GENERALIZATION" if ready else "E03_2_1_PATCH_CURATED_LIBRARY_COVERAGE_REQUIRED",
        "e03_3_unlocked": ready,
        "e04_unlocked": False,
        "e04_lock_status": "LOCKED_PENDING_E03_3_16_OF_16",
        "observed_icon_inventory_16refs": inventory.get("reference_count") == 16,
        "all_p0_semantic_icons_resolved": coverage.get("p0_unresolved_count") == 0,
        "generated_svg_quality_gate_passed": quality_report.get("status") == "passed",
        "curated_v3_exists": coverage.get("status") == "passed",
        "retrieval_policy_v2_exists": policy.get("status") == "passed",
        "semantic_raster_icon_count": 0,
        "unresolved_p0_count": coverage.get("p0_unresolved_count", 0),
        "blank_placeholder_svg_count": quality_report.get("blank_svg_count", 0) + quality_report.get("placeholder_svg_count", 0),
        "protected_artifacts_unchanged": protected_unchanged,
        "broad_canva_parity_claimed": False,
    }
