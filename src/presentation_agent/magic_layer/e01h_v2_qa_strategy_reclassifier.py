"""Reclassify observed E01H-V2 strategy from audit signals."""

from __future__ import annotations

from typing import Any


def reclassify_strategy(signals: dict[str, Any]) -> dict[str, Any]:
    declared = signals.get("declared_strategy")
    actual = declared or "unknown_or_mixed"
    if signals.get("baseline_shortcut_detected") and signals.get("large_blurred_backplate_detected"):
        actual = "text_lift_overlay_baseline"
    elif signals.get("semantic_reconstruction_depth_score", 1.0) < 0.70 and signals.get("internal_label_leakage_count", 0):
        actual = "unknown_or_mixed"
    elif declared == "hybrid_backplate_semantic_native":
        actual = "hybrid_backplate_semantic_native"
    return {
        "schema_name": "strategy_reclassification_report",
        "status": "passed" if actual == declared == "hybrid_backplate_semantic_native" else "failed",
        "declared_strategy": declared,
        "actual_strategy": actual,
        "declared_strategy_matches_observed": actual == declared,
        "reclassified_as_baseline_shortcut": actual in {"text_lift_overlay_baseline", "raster_page_baseline"},
        "canva_parity_claimed": False,
    }
