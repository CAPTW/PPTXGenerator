"""Aggregate Canva+ hybrid gate for E03H-P."""

from __future__ import annotations

from typing import Any


def build_e03h_p_canva_plus_hybrid_gate_report(
    *,
    core_reference_count: int,
    weak_reference_count_after_patch: int,
    all_reference_gates_pass: bool,
    pack_exists: bool,
    semantic_raster_violation_count: int,
    unknown_content_bearing_layer_count: int,
    full_slide_raster_count: int,
    screenshot_slide_count: int,
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "core_12_present": core_reference_count == 12,
        "weak_reference_count_zero": weak_reference_count_after_patch == 0,
        "all_reference_gates_pass": all_reference_gates_pass,
        "patched_pack_exists": pack_exists,
        "semantic_raster_violations_zero": semantic_raster_violation_count == 0,
        "unknown_content_bearing_layers_zero": unknown_content_bearing_layer_count == 0,
        "no_full_slide_reference_background": full_slide_raster_count == 0,
        "no_screenshot_slide": screenshot_slide_count == 0,
        "protected_artifacts_unchanged": protected_artifacts_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e03h_p_canva_plus_hybrid_gate_report",
        "status": "passed" if passed else "failed",
        "decision": "E03H_P_PASS_READY_FOR_E04H_SOURCE_BOUND_SMALL_DECK_WITH_PATCHED_HYBRID_PACK" if passed else "E03H_P_PATCH_WEAK_REFERENCE_QUALITY",
        "checks": checks,
        "e04h_unlocked": passed,
        "e05_unlocked": False,
        "e05_locked": True,
        "canva_parity_claimed": False,
    }


def e03h_p_canva_plus_gate_markdown(report: dict[str, Any]) -> str:
    lines = ["# E03H-P Canva+ Hybrid Gate", "", f"- Status: `{report['status']}`", f"- Decision: `{report['decision']}`", f"- E04H unlocked: `{report['e04h_unlocked']}`", f"- E05 unlocked: `{report['e05_unlocked']}`", "- Broad Canva parity claimed: `False`", ""]
    for key, value in report["checks"].items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines)
