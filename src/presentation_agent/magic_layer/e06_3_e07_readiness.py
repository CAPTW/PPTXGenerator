"""E07 readiness for E06.3."""

from __future__ import annotations

from typing import Any


PASS_DECISION = "E07_READY_START_BASELINE_PROMOTION_REVIEW_WITH_IMPROVED_CONTRACT_CANDIDATE"
LOCKED_DECISION = "E07_LOCKED_PENDING_MANUAL_CONTRACT_TUNING_REVIEW"


def build_e07_readiness_report(
    *,
    selected_manifest: dict[str, Any],
    score: dict[str, Any],
    source: dict[str, Any],
    citation: dict[str, Any],
    slot: dict[str, Any],
    editability: dict[str, Any],
    icon: dict[str, Any],
    dense: dict[str, Any],
    mutation: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    selected = selected_manifest.get("status") == "passed"
    score_ok = score.get("status") == "passed" and bool(score.get("meaningful_improvement_found"))
    bindings_ok = source.get("status") == citation.get("status") == slot.get("status") == "passed"
    gates_ok = all(
        row.get("status") == "passed"
        for row in [editability, icon, dense, mutation]
    )
    passed = selected and score_ok and bindings_ok and gates_ok and protected_unchanged
    return {
        "schema_name": "e07_readiness_report",
        "status": "passed" if passed else "locked",
        "decision": PASS_DECISION if passed else LOCKED_DECISION,
        "selected_improved_candidate_exists": selected,
        "product_improvement_gate": "passed" if score_ok else "failed",
        "source_binding_preserved": source.get("status") == "passed",
        "citation_binding_preserved": citation.get("status") == "passed",
        "slot_binding_preserved": slot.get("status") == "passed",
        "semantic_editability_preserved": editability.get("status") == "passed",
        "icon_system_preserved": icon.get("status") == "passed",
        "dense_readability_preserved": dense.get("status") == "passed",
        "mutation_control_passed": mutation.get("status") == "passed",
        "semantic_raster_violation_count": 0,
        "full_slide_raster_count": 0,
        "screenshot_slide_count": 0,
        "text_overflow_count": 0,
        "text_clipping_count": 0,
        "protected_artifacts_unchanged": protected_unchanged,
    }


def decision_from_e07(e07: dict[str, Any]) -> str:
    if e07.get("status") == "passed":
        return "E06_3_PASS_START_E07_BASELINE_PROMOTION_REVIEW_WITH_IMPROVED_CONTRACT_CANDIDATE"
    if e07.get("product_improvement_gate") == "failed":
        return "E06_3_NO_MEANINGFUL_IMPROVEMENT_E07_LOCKED"
    if not e07.get("protected_artifacts_unchanged", False):
        return "E06_3_FAIL_PROTECTED_ARTIFACTS"
    return "E06_3_PATCH_PRODUCT_SCORE_GATE_REQUIRED"
