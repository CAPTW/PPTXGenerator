"""E00-RX product goal lock helpers."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


class GoalLockError(AssertionError):
    """Raised when a claim conflicts with the locked E00-RX product goal."""


LOCKED_PRODUCT_GOAL: dict[str, Any] = {
    "schema_name": "max_product_goal_statement_v2",
    "decision": "MAX_PRODUCT_GOAL_LOCKED_TO_CANVA_MAGIC_LAYER_PLUS_FIRST",
    "local_only": True,
    "original_long_term_goal": "source_document_to_structured_plan_to_high_quality_large_deck_pptx",
    "current_blocking_product_unit": "reference_image_to_editable_ppt_layer_template_conversion",
    "minimum_benchmark": "canva_magic_layer_visual_segmentation",
    "editability_target": "semantic_ppt_native_reconstruction_beyond_canva",
    "source_bound_deck_generation": "downstream_after_template_conversion_gates",
    "large_deck_scaleout": "blocked_until_e01_e02_e03_e04_pass",
    "blocked_stages": ["D08", "C11", "bulk", "large_deck", "canonical_promotion"],
    "protected_canonical_artifacts": [
        "outputs/editable_template_spec.final.json",
        "outputs/golden_template_masters.pptx",
        "outputs/final_deck_large_premium.pptx",
    ],
    "magic_layer_plus_proven": False,
}


PASS_DECISIONS = {
    "E01_PASS_START_E02_4CORE_MAGIC_LAYER_PLUS",
    "E01_7_PASS_CANVA_PLUS_SINGLE_SLIDE_START_E02_4CORE_MAGIC_LAYER_PLUS",
}


def get_locked_product_goal() -> dict[str, Any]:
    """Return a copy of the locked E00-RX product goal."""

    return deepcopy(LOCKED_PRODUCT_GOAL)


def assert_magic_layer_plus_first(goal: Mapping[str, Any] | None = None) -> bool:
    """Assert that the current product unit remains single-reference Magic Layer+."""

    data = dict(goal or LOCKED_PRODUCT_GOAL)
    expected = "reference_image_to_editable_ppt_layer_template_conversion"
    if data.get("current_blocking_product_unit") != expected:
        raise GoalLockError(
            "Current blocking product unit must remain reference image to editable PPT layer/template conversion."
        )
    if data.get("large_deck_scaleout") not in {
        "blocked_until_e01_e02_e03_e04_pass",
        "downstream_after_e04",
    }:
        raise GoalLockError("Large deck scaleout must remain downstream of Magic Layer+ gates.")
    return True


def assert_no_canva_parity_claim_without_gate(gate_report: str | Path | Mapping[str, Any] | None) -> bool:
    """Reject Canva parity claims unless an explicit passing gate report is supplied."""

    report = _load_mapping(gate_report)
    if not report:
        raise GoalLockError("Canva parity cannot be claimed without a gate report.")

    parity_claimed = bool(report.get("canva_parity_claimed") or report.get("canva_magic_layer_plus_claimed"))
    if not parity_claimed:
        return True

    decision = str(report.get("decision") or report.get("decision_label") or "")
    status = str(report.get("status") or "").lower()
    if decision in PASS_DECISIONS and status in {"passed", "pass"}:
        return True
    if decision in PASS_DECISIONS and report.get("magic_layer_plus_proven") is True:
        return True
    raise GoalLockError("Canva parity claim is overclaimed without an explicit passing Magic Layer+ gate.")


def _load_mapping(value: str | Path | Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    path = Path(value)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
