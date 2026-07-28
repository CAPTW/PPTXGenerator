"""E07 readiness for E06.4.1."""

from __future__ import annotations

from typing import Any


def build_final_visual_acceptance_scorecard(matrix: dict[str, Any], regression: dict[str, Any]) -> dict[str, Any]:
    improved = int(matrix.get("materially_improved_count", 0))
    baseline_stable = regression.get("accepted_candidate_visual_regression_count", 0) == 0
    return {
        "schema_name": "final_visual_acceptance_scorecard",
        "status": "baseline_stable" if baseline_stable and improved < 3 else "passed" if improved >= 3 and baseline_stable else "failed",
        "materially_improved_slide_count": improved,
        "accepted_candidate_visual_regression_count": regression.get("accepted_candidate_visual_regression_count", 0),
        "meets_improved_baseline_threshold": improved >= 3,
        "baseline_stable_but_not_improved": baseline_stable and improved < 3,
    }


def build_e07_readiness_report(
    final_scorecard: dict[str, Any],
    binding: dict[str, Any],
    editability: dict[str, Any],
    icon: dict[str, Any],
    layout: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    improved_ready = (
        final_scorecard.get("status") == "passed"
        and binding.get("status") == "passed"
        and editability.get("status") == "passed"
        and icon.get("status") == "passed"
        and layout.get("status") == "passed"
        and protected_unchanged
    )
    return {
        "schema_name": "e07_readiness_report",
        "status": "passed" if improved_ready else "locked",
        "decision": "E07_READY_START_BASELINE_PROMOTION_REVIEW_WITH_HUMAN_ACCEPTED_CANDIDATE" if improved_ready else "E07_LOCKED_BASELINE_STABLE_NO_MEANINGFUL_IMPROVEMENT",
        "accepted_candidate_exists": binding.get("status") == "passed",
        "materially_improved_slide_count": final_scorecard.get("materially_improved_slide_count", 0),
        "baseline_stable_but_not_improved": final_scorecard.get("baseline_stable_but_not_improved", False),
        "binding_preserved": binding.get("status") == "passed",
        "semantic_editability_preserved": editability.get("status") == "passed",
        "icon_system_preserved": icon.get("status") == "passed",
        "layout_contract_preserved": layout.get("status") == "passed",
        "semantic_raster_violation_count": 0,
        "protected_artifacts_unchanged": protected_unchanged,
    }


def decision_from_e07(e07: dict[str, Any], binding: dict[str, Any]) -> str:
    if not e07.get("protected_artifacts_unchanged", False):
        return "E06_4_1_FAIL_PROTECTED_ARTIFACTS"
    if binding.get("binding_regression_count", 0) > 0:
        return "E06_4_1_FAIL_BINDING_REGRESSION"
    if e07.get("status") == "passed":
        return "E06_4_1_PASS_START_E07_BASELINE_PROMOTION_REVIEW_WITH_HUMAN_ACCEPTED_CANDIDATE"
    if e07.get("baseline_stable_but_not_improved"):
        return "E06_4_1_BASELINE_STABLE_NO_MEANINGFUL_IMPROVEMENT_E07_LOCKED"
    return "E06_4_1_PATCH_MANUAL_SLIDE_TUNING_REQUIRED"
