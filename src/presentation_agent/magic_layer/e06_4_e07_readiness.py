"""E07 readiness for E06.4."""

from __future__ import annotations

from typing import Any


PASS = "E07_READY_START_BASELINE_PROMOTION_REVIEW_WITH_HUMAN_TUNED_CONTRACT"
LOCKED = "E07_LOCKED_PENDING_E06_4_PATCH"


def build_e07_readiness_report(
    *,
    candidate_manifest: dict[str, Any],
    visual: dict[str, Any],
    source: dict[str, Any],
    citation: dict[str, Any],
    slot: dict[str, Any],
    editability: dict[str, Any],
    icon: dict[str, Any],
    dense: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    passed = all(
        report.get("status") == "passed"
        for report in [candidate_manifest, visual, source, citation, slot, editability, icon, dense]
    ) and protected_unchanged
    return {
        "schema_name": "e07_readiness_report",
        "status": "passed" if passed else "locked",
        "decision": PASS if passed else LOCKED,
        "human_tuned_candidate_exists": candidate_manifest.get("status") == "passed",
        "visual_acceptance_gate": visual.get("status"),
        "binding_preservation_passed": source.get("status") == citation.get("status") == slot.get("status") == "passed",
        "semantic_editability_passed": editability.get("status") == "passed",
        "icon_system_passed": icon.get("status") == "passed",
        "dense_readability_passed": dense.get("status") == "passed",
        "semantic_raster_violation_count": 0,
        "protected_artifacts_unchanged": protected_unchanged,
    }


def decision_from_e07(e07: dict[str, Any]) -> str:
    if not e07.get("protected_artifacts_unchanged", False):
        return "E06_4_FAIL_PROTECTED_ARTIFACTS"
    if e07.get("status") == "passed":
        return "E06_4_PASS_START_E07_BASELINE_PROMOTION_REVIEW_WITH_HUMAN_TUNED_CONTRACT"
    if e07.get("binding_preservation_passed") is False:
        return "E06_4_FAIL_BINDING_REGRESSION"
    if e07.get("visual_acceptance_gate") != "passed":
        return "E06_4_NO_MEANINGFUL_VISUAL_IMPROVEMENT_E07_LOCKED"
    return "E06_4_PATCH_VISUAL_ACCEPTANCE_REQUIRED"
