from __future__ import annotations

from typing import Any


def build_source_binding_preparation(binding_rules: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    binding_rules = binding_rules or []
    preparedness = "partial" if binding_rules else False
    return {
        "source_binding_preparedness": preparedness,
        "source_bound_deck_generated": False,
        "source_bound_readiness": False,
        "required_for_future_e04": [
            "stable_slots",
            "binding_rules",
            "overflow_policies",
            "citation/source_slots",
            "chart/table data editability expectations",
            "source traceability fields",
            "rejection policy for overflow/unbound data",
        ],
        "limitations": ["T01 does not bind source documents or generate source-bound decks."],
        "validation_summary": {"binding_rule_count": len(binding_rules)},
    }


def validate_source_binding_preparation(preparation: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if preparation.get("source_bound_deck_generated") is True:
        failures.append("source_bound_deck_generated must be false")
    if preparation.get("source_bound_readiness") is True:
        failures.append("source_bound_readiness must not be true in T01")
    return {"pass": not failures, "failures": failures}
