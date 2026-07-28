"""Quality gate for E04H-BP true hybrid visual backplate transfer."""

from __future__ import annotations

from typing import Any


def build_e04h_bp_gate_report(
    *,
    clone_report: dict[str, Any],
    semantic_substitution_passed: bool,
    svg_provenance_passed: bool,
    native_chart_table_passed: bool,
    citation_coverage_passed: bool,
    semantic_raster_violation_count: int,
    unknown_content_bearing_layer_count: int,
    text_overflow_count: int,
    text_truncation_count: int,
    internal_label_leakage_count: int,
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    has_media_or_equivalent = (
        clone_report.get("source_bound_deck_media_count", 0) > 0
        and clone_report.get("source_bound_deck_picture_object_count", 0) > 0
    ) or clone_report.get("documented_equivalent_native_visual_backplate_groups", 0) > 0
    checks = {
        "visual_backplate_transfer_coverage_passes": clone_report.get("visual_backplate_transfer_coverage", 0.0) >= 0.75,
        "source_bound_deck_has_media_or_native_backplate_equivalent": has_media_or_equivalent,
        "selected_reference_visual_identity_recognizable": clone_report.get("status") == "passed",
        "semantic_layer_substitution_passes": semantic_substitution_passed,
        "svg_provenance_survives": svg_provenance_passed,
        "native_chart_table_binding_passes": native_chart_table_passed,
        "citation_coverage_passes": citation_coverage_passed,
        "semantic_raster_violations_zero": semantic_raster_violation_count == 0,
        "unknown_content_bearing_layers_zero": unknown_content_bearing_layer_count == 0,
        "no_full_slide_reference_background": clone_report.get("full_slide_reference_background_count", 1) == 0,
        "no_screenshot_slide": clone_report.get("screenshot_slide_count", 1) == 0,
        "text_overflow_zero": text_overflow_count == 0,
        "text_truncation_zero": text_truncation_count == 0,
        "internal_label_leakage_zero": internal_label_leakage_count == 0,
        "protected_artifacts_unchanged": protected_artifacts_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e04h_bp_canva_plus_hybrid_source_deck_gate_report",
        "status": "passed" if passed else "failed",
        "decision": "E04H_BP_PASS_READY_FOR_E05_34_SLIDE_SCALEOUT_WITH_TRUE_HYBRID_TRANSFER" if passed else _patch_decision(checks),
        "checks": checks,
        "visual_backplate_transfer_coverage": clone_report.get("visual_backplate_transfer_coverage", 0.0),
        "source_bound_deck_media_count": clone_report.get("source_bound_deck_media_count", 0),
        "source_bound_deck_picture_object_count": clone_report.get("source_bound_deck_picture_object_count", 0),
        "semantic_raster_violation_count": semantic_raster_violation_count,
        "unknown_content_bearing_layer_count": unknown_content_bearing_layer_count,
        "e05_unlocked": passed,
        "canva_parity_claimed": False,
    }


def _patch_decision(checks: dict[str, bool]) -> str:
    if not checks["protected_artifacts_unchanged"]:
        return "E04H_BP_FAIL_PROTECTED_ARTIFACTS"
    if not checks["semantic_layer_substitution_passes"] or not checks["semantic_raster_violations_zero"]:
        return "E04H_BP_FAIL_SEMANTIC_EDITABILITY"
    if not checks["visual_backplate_transfer_coverage_passes"]:
        return "E04H_BP_PATCH_CLONE_BASED_REBINDING"
    if not checks["source_bound_deck_has_media_or_native_backplate_equivalent"]:
        return "E04H_BP_PATCH_VISUAL_BACKPLATE_BINDING"
    if not checks["svg_provenance_survives"]:
        return "E04H_BP_PATCH_SEMANTIC_LAYER_SUBSTITUTION"
    return "E04H_BP_FAIL_VISUAL_BACKPLATE_TRANSFER"
