"""Reject clone substitution scaffolding and duplicate chrome."""

from __future__ import annotations

from typing import Any


SCAFFOLD_ROLES = {
    "placeholder_box",
    "debug_bounding_box",
    "empty_slot_frame",
    "duplicate_component_border",
    "duplicate_table_grid",
    "duplicate_chart_frame",
    "duplicate_card_outline",
    "source_footer_duplicate",
}


def evaluate_clone_guard(plan: dict[str, Any]) -> dict[str, Any]:
    layers = plan.get("candidate_layers", [])
    flagged = [layer for layer in layers if layer.get("role") in SCAFFOLD_ROLES]
    return {
        "schema_name": "clone_scaffold_rejection_report",
        "status": "passed" if not flagged else "failed",
        "clone_strategy_allowed": not flagged,
        "scaffold_or_duplicate_chrome_count": len(flagged),
        "flagged_layers": flagged,
        "duplicate_chrome_count": sum(1 for layer in flagged if "duplicate" in layer.get("role", "")),
        "canva_parity_claimed": False,
    }
