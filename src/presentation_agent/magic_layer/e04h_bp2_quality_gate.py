"""Quality gate for E04H-BP2 cleaned hybrid transfer."""

from __future__ import annotations

from typing import Any


def build_bp2_quality_gate_report(
    *,
    visual_clutter_score_before: float,
    visual_clutter_score_after: float,
    useful_visual_backplate_coverage: float,
    duplicate_chrome_count: int,
    scaffold_backplate_count: int,
    media_count: int,
    picture_object_count: int,
    semantic_raster_violation_count: int,
    unknown_content_bearing_layer_count: int,
    svg_provenance_coverage: float,
    chart_table_native_binding_passed: bool,
    text_overflow_count: int,
    text_truncation_count: int,
    internal_label_leakage_count: int,
    citation_coverage_passed: bool,
    full_slide_reference_background_count: int,
    screenshot_slide_count: int,
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "visual_clutter_score_decreased": visual_clutter_score_after < visual_clutter_score_before,
        "useful_visual_backplate_coverage_meaningful": useful_visual_backplate_coverage >= 0.75,
        "media_backplates_retained": media_count > 0 and picture_object_count > 0,
        "duplicate_chrome_zero": duplicate_chrome_count == 0,
        "scaffold_backplates_zero": scaffold_backplate_count == 0,
        "semantic_raster_violations_zero": semantic_raster_violation_count == 0,
        "unknown_content_bearing_layers_zero": unknown_content_bearing_layer_count == 0,
        "svg_provenance_coverage_1": svg_provenance_coverage == 1.0,
        "chart_table_native_binding_passes": chart_table_native_binding_passed,
        "text_overflow_zero": text_overflow_count == 0,
        "text_truncation_zero": text_truncation_count == 0,
        "internal_label_leakage_zero": internal_label_leakage_count == 0,
        "citation_coverage_passes": citation_coverage_passed,
        "no_full_slide_reference_background": full_slide_reference_background_count == 0,
        "no_screenshot_slide": screenshot_slide_count == 0,
        "protected_artifacts_unchanged": protected_artifacts_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e04h_bp2_canva_plus_hybrid_source_deck_gate_report",
        "status": "passed" if passed else "failed",
        "decision": "E04H_BP2_PASS_READY_FOR_E05_34_SLIDE_SCALEOUT_WITH_CLEAN_HYBRID_TRANSFER" if passed else _patch_decision(checks),
        "checks": checks,
        "visual_clutter_score_before": visual_clutter_score_before,
        "visual_clutter_score_after": visual_clutter_score_after,
        "visual_clutter_delta": visual_clutter_score_before - visual_clutter_score_after,
        "useful_visual_backplate_coverage": useful_visual_backplate_coverage,
        "duplicate_chrome_count": duplicate_chrome_count,
        "scaffold_backplate_count": scaffold_backplate_count,
        "e05_unlocked": passed,
        "canva_parity_claimed": False,
    }


def _patch_decision(checks: dict[str, bool]) -> str:
    if not checks["protected_artifacts_unchanged"]:
        return "E04H_BP2_FAIL_PROTECTED_ARTIFACTS"
    if not checks["semantic_raster_violations_zero"] or not checks["unknown_content_bearing_layers_zero"]:
        return "E04H_BP2_FAIL_SEMANTIC_EDITABILITY"
    if not checks["duplicate_chrome_zero"]:
        return "E04H_BP2_PATCH_DUPLICATE_CHROME_REMOVAL"
    if not checks["scaffold_backplates_zero"]:
        return "E04H_BP2_PATCH_BACKPLATE_CLASSIFICATION"
    if not checks["useful_visual_backplate_coverage_meaningful"] or not checks["media_backplates_retained"]:
        return "E04H_BP2_PATCH_VISUAL_RICHNESS_RETENTION"
    if not checks["visual_clutter_score_decreased"]:
        return "E04H_BP2_FAIL_DESIGN_QUALITY"
    return "E04H_BP2_PATCH_SEMANTIC_LAYER_SUBSTITUTION"
