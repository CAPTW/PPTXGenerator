"""Classify actual strategy used by E01H-V2-R1 output."""

from __future__ import annotations

from typing import Any


def classify_r1_strategy(signals: dict[str, Any]) -> dict[str, Any]:
    actual = "hybrid_backplate_semantic_native"
    if signals.get("full_reference_backplate_detected") or signals.get("internal_label_leakage_count", 0) > 0:
        actual = "text_lift_overlay_baseline"
    elif signals.get("semantic_reconstruction_depth_score", 0.0) < 0.70:
        actual = "unknown_or_mixed"
    elif signals.get("segmented_backplate_count", 0) == 0:
        actual = "native_shape_reconstruction_baseline"
    return {
        "schema_name": "actual_strategy_classification_report",
        "status": "passed" if actual in {"hybrid_backplate_semantic_native", "native_shape_reconstruction_baseline"} else "failed",
        "declared_strategy": signals.get("declared_strategy"),
        "actual_strategy": actual,
        "classified_as_text_lift_overlay_baseline": actual == "text_lift_overlay_baseline",
        "canva_parity_claimed": False,
    }
