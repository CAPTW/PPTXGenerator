"""Strict E01.4 observed icon parsing gate."""

from __future__ import annotations

from typing import Any


def evaluate_e01_4_canva_plus_gate(candidate: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    high_risks: list[str] = []
    if candidate.get("vision_svg_trace_available") is not True:
        blockers.append("vision_svg_trace_unavailable")
    for key, failure in {
        "candidate_renders": "candidate_render_missing",
        "no_full_slide_reference_background": "full_slide_reference_background",
        "no_screenshot_slide": "screenshot_slide",
        "all_observed_icon_crops_resolved": "observed_icon_crop_unresolved",
        "exact_or_trace_only": "non_exact_or_non_trace_icon_resolution",
        "generated_svg_policy_pass": "generated_svg_policy_failed",
        "generated_icon_library_pass": "generated_icon_library_failed",
        "svg_insertion_pass": "svg_insertion_failed",
        "checklist_icon_exactness_pass": "checklist_icon_exactness_failed",
        "bottom_action_icon_exactness_pass": "bottom_action_icon_exactness_failed",
        "text_run_formatting_pass": "text_run_formatting_failed",
        "source_svg_files_unchanged": "source_svg_modified",
        "protected_artifacts_unchanged": "protected_artifacts_changed",
    }.items():
        if candidate.get(key) is not True:
            blockers.append(failure)
    if int(candidate.get("semantic_raster_violation_count", 0)) > 0:
        blockers.append("semantic_raster_violations")
    if int(candidate.get("unknown_content_bearing_layer_count", 0)) > 0:
        blockers.append("unknown_content_bearing_layers")
    if int(candidate.get("text_overflow_count", 0)) > 0:
        blockers.append("text_overflow")
    if int(candidate.get("severe_layout_overlap_count", 0)) > 0:
        blockers.append("severe_layout_overlap")
    if int(candidate.get("procedural_icon_fallback_count", 0)) > 0:
        blockers.append("procedural_icon_fallback_used")
    if int(candidate.get("generic_icon_count", 0)) > 0:
        blockers.append("generic_icon_used")
    if candidate.get("visual_no_regression_from_e01_3") is not True:
        blockers.append("visual_regression_from_e01_3")
    if candidate.get("final_layer_segmentation_target_met") is not True:
        high_risks.append("layer_segmentation_fidelity_still_below_final_target")

    if "vision_svg_trace_unavailable" in blockers:
        decision = "E01_4_BLOCKED_VISION_SVG_TRACE_UNAVAILABLE"
    elif blockers:
        decision = _patch_decision(blockers)
    elif high_risks:
        decision = "E01_4_PASS_START_E01_5_LAYER_SEGMENTATION_POLISH"
    else:
        decision = "E01_4_PASS_UNLOCK_E02_CONTROLLED_BATCH_CONVERSION"
    return {
        "schema_name": "canva_plus_gate_report_e01_4",
        "status": "passed" if not blockers else "failed",
        "decision": decision,
        "e02_unlocked": decision == "E01_4_PASS_UNLOCK_E02_CONTROLLED_BATCH_CONVERSION",
        "e01_5_unlocked": decision == "E01_4_PASS_START_E01_5_LAYER_SEGMENTATION_POLISH",
        "blockers": blockers,
        "high_product_risks": high_risks,
        "canva_parity_claimed": False,
    }


def _patch_decision(blockers: list[str]) -> str:
    if "observed_icon_crop_unresolved" in blockers:
        return "E01_4_PATCH_ICON_CROP_DETECTION"
    if "non_exact_or_non_trace_icon_resolution" in blockers:
        return "E01_4_PATCH_LIBRARY_EXACT_MATCH"
    if "generated_svg_policy_failed" in blockers:
        return "E01_4_PATCH_VISION_SVG_TRACE"
    if "generated_icon_library_failed" in blockers:
        return "E01_4_PATCH_GENERATED_ICON_LIBRARY"
    if "svg_insertion_failed" in blockers:
        return "E01_4_PATCH_SVG_INSERTION"
    if "semantic_raster_violations" in blockers or "procedural_icon_fallback_used" in blockers or "generic_icon_used" in blockers:
        return "E01_4_FAIL_SEMANTIC_ICON_VECTOR_GATE"
    return "E01_4_FAIL_CANVA_LAYER_TARGET"
