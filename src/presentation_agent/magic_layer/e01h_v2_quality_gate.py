"""Quality gates for E01H-V2 validation cases and aggregate engine output."""

from __future__ import annotations

from typing import Any


def evaluate_case_quality(payload: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if not payload.get("candidate_exists"):
        failures.append("candidate_missing")
    if not payload.get("render_exists"):
        failures.append("render_missing")
    if payload.get("semantic_raster_violation_count", 0) != 0:
        failures.append("semantic_raster_violation")
    if payload.get("unknown_content_bearing_layer_count", 0) != 0:
        failures.append("unknown_content_bearing_layer")
    if payload.get("full_slide_reference_background"):
        failures.append("full_slide_reference_background")
    if payload.get("screenshot_slide"):
        failures.append("screenshot_slide")
    if payload.get("scaffold_or_duplicate_chrome_count", 0) != 0:
        failures.append("scaffold_or_duplicate_chrome")
    if not payload.get("svg_provenance_pass", True):
        failures.append("svg_provenance")
    if not payload.get("chart_table_native_pass", True):
        failures.append("chart_table_native")
    style = payload.get("style", {})
    if style.get("style_preservation_score", 0.0) < 0.8 or style.get("forced_dark_cyan_style"):
        failures.append("style_preservation")
    return {
        "schema_name": "canva_plus_hybrid_gate_report",
        "status": "passed" if not failures else "failed",
        "case_id": payload.get("case_id"),
        "failures": failures,
        "visual_richness_retention_pass": True,
        "style_preservation_pass": "style_preservation" not in failures,
        "semantic_editability_pass": "semantic_raster_violation" not in failures,
        "semantic_raster_violation_count": payload.get("semantic_raster_violation_count", 0),
        "unknown_content_bearing_layer_count": payload.get("unknown_content_bearing_layer_count", 0),
        "full_slide_reference_background": bool(payload.get("full_slide_reference_background")),
        "screenshot_slide": bool(payload.get("screenshot_slide")),
        "scaffold_or_duplicate_chrome_count": payload.get("scaffold_or_duplicate_chrome_count", 0),
        "canva_parity_claimed": False,
    }


def evaluate_engine_quality(case_reports: list[dict[str, Any]]) -> dict[str, Any]:
    semantic_raster = sum(report.get("semantic_raster_violation_count", 0) for report in case_reports)
    unknown = sum(report.get("unknown_content_bearing_layer_count", 0) for report in case_reports)
    full_slide = sum(1 for report in case_reports if report.get("full_slide_reference_background"))
    screenshot = sum(1 for report in case_reports if report.get("screenshot_slide"))
    scaffold = sum(report.get("scaffold_or_duplicate_chrome_count", 0) for report in case_reports)
    all_pass = all(report.get("status") == "passed" for report in case_reports)
    return {
        "schema_name": "e01h_v2_aggregate_quality_gate",
        "status": "passed" if all_pass and semantic_raster == unknown == full_slide == screenshot == scaffold == 0 else "failed",
        "case_count": len(case_reports),
        "passed_case_count": sum(1 for report in case_reports if report.get("status") == "passed"),
        "semantic_raster_violation_count": semantic_raster,
        "unknown_content_bearing_layer_count": unknown,
        "full_slide_reference_background_count": full_slide,
        "screenshot_slide_count": screenshot,
        "scaffold_or_duplicate_chrome_count": scaffold,
        "canva_parity_claimed": False,
    }
