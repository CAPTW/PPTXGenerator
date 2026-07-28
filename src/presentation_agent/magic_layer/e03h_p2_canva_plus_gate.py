"""Aggregate and per-reference gate logic for E03H-P2."""

from __future__ import annotations

from typing import Any


def build_e03h_p2_canva_plus_hybrid_gate_report(
    *,
    core_reference_count: int,
    all_reference_gates_pass: bool,
    pack_exists: bool,
    required_semantic_icon_svg_bound_coverage: float,
    optional_semantic_icon_svg_bound_coverage: float,
    semantic_icon_raster_fallback_count: int,
    empty_circle_placeholder_count: int,
    procedural_native_without_source_count: int,
    semantic_raster_violation_count: int,
    unknown_content_bearing_layer_count: int,
    full_slide_reference_background_count: int,
    screenshot_slide_count: int,
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "core_12_present": core_reference_count == 12,
        "all_reference_gates_pass": all_reference_gates_pass,
        "svg_rebound_pack_exists": pack_exists,
        "required_semantic_icon_svg_bound_coverage_1": required_semantic_icon_svg_bound_coverage == 1.0,
        "optional_semantic_icon_svg_bound_coverage_ok": optional_semantic_icon_svg_bound_coverage >= 0.9,
        "semantic_icon_raster_fallback_zero": semantic_icon_raster_fallback_count == 0,
        "empty_circle_placeholder_zero": empty_circle_placeholder_count == 0,
        "procedural_native_without_source_zero": procedural_native_without_source_count == 0,
        "semantic_raster_violations_zero": semantic_raster_violation_count == 0,
        "unknown_content_bearing_layers_zero": unknown_content_bearing_layer_count == 0,
        "no_full_slide_reference_background": full_slide_reference_background_count == 0,
        "no_screenshot_slide": screenshot_slide_count == 0,
        "protected_artifacts_unchanged": protected_artifacts_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e03h_p2_canva_plus_hybrid_gate_report",
        "status": "passed" if passed else "failed",
        "decision": "E03H_P2_PASS_READY_FOR_E04H_SOURCE_BOUND_SMALL_DECK_WITH_SVG_BOUND_HYBRID_PACK" if passed else _patch_decision(checks),
        "checks": checks,
        "e04h_unlocked": passed,
        "e05_unlocked": False,
        "canva_parity_claimed": False,
    }


def _patch_decision(checks: dict[str, bool]) -> str:
    if not checks["required_semantic_icon_svg_bound_coverage_1"]:
        return "E03H_P2_FAIL_SEMANTIC_ICON_SVG_BINDING"
    if not checks["semantic_icon_raster_fallback_zero"] or not checks["empty_circle_placeholder_zero"] or not checks["procedural_native_without_source_zero"]:
        return "E03H_P2_FAIL_SEMANTIC_ICON_SVG_BINDING"
    if not checks["semantic_raster_violations_zero"] or not checks["unknown_content_bearing_layers_zero"]:
        return "E03H_P2_FAIL_SEMANTIC_EDITABILITY"
    if not checks["svg_rebound_pack_exists"]:
        return "E03H_P2_PATCH_PACKAGE_PROVENANCE"
    return "E03H_P2_PATCH_ICON_REBINDING"
