"""Quality gate for E04H source-bound hybrid deck."""

from __future__ import annotations

from typing import Any


def build_e04h_canva_plus_hybrid_source_deck_gate_report(
    *,
    deck_exists: bool,
    deck_rendered: bool,
    source_trace_passed: bool,
    citation_coverage_passed: bool,
    semantic_editability_passed: bool,
    svg_provenance_passed: bool,
    native_chart_table_passed: bool,
    visual_richness_passed: bool,
    text_overflow_count: int,
    text_truncation_count: int,
    internal_label_leakage_count: int,
    semantic_raster_violation_count: int,
    unknown_content_bearing_layer_count: int,
    full_slide_reference_background_count: int,
    screenshot_slide_count: int,
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "source_bound_hybrid_deck_exists": deck_exists,
        "source_bound_hybrid_deck_renders": deck_rendered,
        "source_traceability_passes": source_trace_passed,
        "citation_coverage_passes": citation_coverage_passed,
        "semantic_editability_passes": semantic_editability_passed,
        "svg_provenance_passes": svg_provenance_passed,
        "native_chart_table_binding_passes": native_chart_table_passed,
        "visual_richness_retention_passes": visual_richness_passed,
        "text_overflow_zero": text_overflow_count == 0,
        "text_truncation_zero": text_truncation_count == 0,
        "internal_label_leakage_zero": internal_label_leakage_count == 0,
        "semantic_raster_violations_zero": semantic_raster_violation_count == 0,
        "unknown_content_bearing_layers_zero": unknown_content_bearing_layer_count == 0,
        "no_full_slide_reference_background": full_slide_reference_background_count == 0,
        "no_screenshot_slide": screenshot_slide_count == 0,
        "protected_artifacts_unchanged": protected_artifacts_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e04h_canva_plus_hybrid_source_deck_gate_report",
        "status": "passed" if passed else "failed",
        "decision": "E04H_PASS_READY_FOR_E05_34_SLIDE_SCALEOUT_WITH_HYBRID_PACK" if passed else _patch_decision(checks),
        "checks": checks,
        "e05_unlocked": passed,
        "canva_parity_claimed": False,
    }


def _patch_decision(checks: dict[str, bool]) -> str:
    if not checks["semantic_editability_passes"] or not checks["semantic_raster_violations_zero"]:
        return "E04H_FAIL_SEMANTIC_EDITABILITY"
    if not checks["svg_provenance_passes"]:
        return "E04H_PATCH_SVG_ICON_PROVENANCE"
    if not checks["native_chart_table_binding_passes"]:
        return "E04H_PATCH_CHART_BINDING"
    if not checks["source_traceability_passes"] or not checks["citation_coverage_passes"]:
        return "E04H_PATCH_SOURCE_TRACE"
    if not checks["text_overflow_zero"] or not checks["text_truncation_zero"]:
        return "E04H_PATCH_TEXT_OVERFLOW"
    if not checks["visual_richness_retention_passes"]:
        return "E04H_PATCH_VISUAL_QUALITY"
    return "E04H_PATCH_SLOT_BINDING"
