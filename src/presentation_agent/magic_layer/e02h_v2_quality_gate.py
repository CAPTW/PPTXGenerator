"""Quality gates for E02H-V2 holdout generalization."""

from __future__ import annotations

from typing import Any


def evaluate_e02h_v2_case_gate(signals: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if signals.get("internal_label_leakage_count", 0) != 0:
        failures.append("internal_label_leakage")
    if signals.get("full_reference_backplate_detected"):
        failures.append("full_reference_backplate")
    if signals.get("actual_strategy") == "text_lift_overlay_baseline":
        failures.append("text_lift_overlay_baseline")
    if signals.get("actual_strategy") == "raster_page_baseline":
        failures.append("raster_page_baseline")
    if signals.get("semantic_reconstruction_depth_score", 0.0) < 0.70:
        failures.append("semantic_reconstruction_depth")
    for key in ["semantic_raster_violation_count", "unknown_content_bearing_layer_count", "scaffold_or_duplicate_chrome_count"]:
        if signals.get(key, 0) != 0:
            failures.append(key)
    for key in ["full_slide_reference_background", "screenshot_slide"]:
        if signals.get(key):
            failures.append(key)
    for key in ["style_preservation_pass", "visual_richness_retention_pass", "semantic_editability_pass"]:
        if signals.get(key) is False:
            failures.append(key)
    return {
        "schema_name": "canva_plus_hybrid_gate_report",
        "status": "passed" if not failures else "failed",
        "case_id": signals.get("case_id"),
        "failures": failures,
        "actual_strategy": signals.get("actual_strategy"),
        "internal_label_leakage_count": signals.get("internal_label_leakage_count", 0),
        "full_reference_backplate_detected": bool(signals.get("full_reference_backplate_detected")),
        "semantic_reconstruction_depth_score": signals.get("semantic_reconstruction_depth_score", 0.0),
        "semantic_raster_violation_count": signals.get("semantic_raster_violation_count", 0),
        "unknown_content_bearing_layer_count": signals.get("unknown_content_bearing_layer_count", 0),
        "full_slide_reference_background": bool(signals.get("full_slide_reference_background")),
        "screenshot_slide": bool(signals.get("screenshot_slide")),
        "scaffold_or_duplicate_chrome_count": signals.get("scaffold_or_duplicate_chrome_count", 0),
        "canva_parity_claimed": False,
    }


def evaluate_e02h_v2_aggregate_gate(case_reports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": "e02h_v2_aggregate_gate",
        "status": "passed" if case_reports and all(report.get("status") == "passed" for report in case_reports) else "failed",
        "case_count": len(case_reports),
        "passed_case_count": sum(1 for report in case_reports if report.get("status") == "passed"),
        "internal_label_leakage_count": sum(report.get("internal_label_leakage_count", 0) for report in case_reports),
        "text_lift_overlay_reclassified_count": sum(1 for report in case_reports if report.get("actual_strategy") == "text_lift_overlay_baseline"),
        "semantic_raster_violation_count": sum(report.get("semantic_raster_violation_count", 0) for report in case_reports),
        "unknown_content_bearing_layer_count": sum(report.get("unknown_content_bearing_layer_count", 0) for report in case_reports),
        "full_slide_reference_background_count": sum(1 for report in case_reports if report.get("full_slide_reference_background")),
        "screenshot_slide_count": sum(1 for report in case_reports if report.get("screenshot_slide")),
        "canva_parity_claimed": False,
    }
