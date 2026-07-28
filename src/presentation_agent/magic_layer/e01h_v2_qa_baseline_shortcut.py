"""Detect baseline shortcuts in declared E01H-V2 hybrid candidates."""

from __future__ import annotations

from typing import Any


def detect_baseline_shortcut(signals: dict[str, Any]) -> dict[str, Any]:
    declared = signals.get("declared_strategy")
    large_picture = signals.get("largest_picture_area_ratio", 0.0) >= 0.55 and signals.get("picture_object_count", 0) <= 2
    reference_like_name = any(token in str(signals.get("picture_name", "")).lower() for token in ["backplate", "reference", "page"])
    low_depth = signals.get("semantic_reconstruction_depth_score", 1.0) < 0.70
    label_leak = signals.get("internal_label_leakage_count", 0) > 0
    detected = declared == "hybrid_backplate_semantic_native" and large_picture and reference_like_name and (low_depth or label_leak)
    return {
        "schema_name": "baseline_shortcut_detection_report",
        "status": "passed" if not detected else "failed",
        "declared_strategy": declared,
        "baseline_shortcut_detected": detected,
        "large_single_picture_backplate": large_picture,
        "reference_like_backplate_name": reference_like_name,
        "low_semantic_reconstruction_depth": low_depth,
        "internal_label_leakage_contributed": label_leak,
        "resembles_text_lift_overlay_baseline": detected,
        "canva_parity_claimed": False,
    }
