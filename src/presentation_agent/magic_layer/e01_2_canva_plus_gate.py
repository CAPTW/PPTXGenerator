"""Strict E01.2 Canva+ gate."""

from __future__ import annotations

from typing import Any


def evaluate_e01_2_canva_plus_gate(candidate: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    high_risks: list[str] = []

    checks = {
        "candidate_renders": "candidate_render_missing",
        "no_full_slide_reference_background": "full_slide_reference_background",
        "no_screenshot_slide": "screenshot_slide",
        "text_run_formatting_pass": "text_run_formatting_defect",
        "text_contrast_capacity_pass": "text_contrast_or_capacity_defect",
        "checklist_geometry_pass": "checklist_geometry_defect",
        "svg_role_promotion_pass": "svg_role_promotion_defect",
        "bottom_action_bar_pass": "bottom_action_bar_defect",
        "source_footer_pass": "source_footer_defect",
        "thumbnail_callout_pass": "thumbnail_callout_defect",
        "hero_layer_segmentation_pass": "hero_layer_segmentation_defect",
        "technical_overlay_pass": "technical_overlay_defect",
    }
    for key, failure in checks.items():
        if candidate.get(key) is not True:
            blockers.append(failure)

    if int(candidate.get("unknown_content_bearing_layer_count", 0)) > 0:
        blockers.append("unknown_content_bearing_layers")
    if int(candidate.get("semantic_raster_violation_count", 0)) > 0:
        blockers.append("semantic_raster_violations")
    if int(candidate.get("text_overflow_count", 0)) > 0:
        blockers.append("text_overflow")
    if int(candidate.get("severe_layout_overlap_count", 0)) > 0:
        blockers.append("severe_layout_overlap")

    if candidate.get("checklist_region_improved") is not True:
        high_risks.append("checklist_region_not_improved")
    if candidate.get("bottom_action_region_improved") is not True:
        high_risks.append("bottom_action_region_not_improved")
    if candidate.get("visual_fidelity_target_met") is not True:
        high_risks.append("visual_fidelity_still_below_final_canva_target")

    if blockers:
        decision = _patch_decision(blockers)
    elif high_risks:
        decision = "E01_2_PASS_START_E01_3_LAYER_SEGMENTATION_POLISH"
    else:
        decision = "E01_2_PASS_UNLOCK_E02_CONTROLLED_BATCH_CONVERSION"

    return {
        "schema_name": "canva_plus_gate_report_e01_2",
        "status": "passed" if not blockers else "failed",
        "decision": decision,
        "e02_unlocked": decision == "E01_2_PASS_UNLOCK_E02_CONTROLLED_BATCH_CONVERSION",
        "e01_3_unlocked": decision == "E01_2_PASS_START_E01_3_LAYER_SEGMENTATION_POLISH",
        "blockers": blockers,
        "high_product_risks": high_risks,
        "canva_parity_claimed": decision == "E01_2_PASS_UNLOCK_E02_CONTROLLED_BATCH_CONVERSION",
    }


def _patch_decision(blockers: list[str]) -> str:
    if "semantic_raster_violations" in blockers or "svg_role_promotion_defect" in blockers:
        return "E01_2_FAIL_SEMANTIC_EDITABILITY"
    if "text_run_formatting_defect" in blockers or "text_contrast_or_capacity_defect" in blockers or "text_overflow" in blockers:
        return "E01_2_PATCH_TEXT_RUN_FORMATTING"
    if "checklist_geometry_defect" in blockers:
        return "E01_2_PATCH_CHECKLIST_GEOMETRY"
    if "bottom_action_bar_defect" in blockers:
        return "E01_2_PATCH_BOTTOM_ACTION_BAR"
    if "hero_layer_segmentation_defect" in blockers:
        return "E01_2_PATCH_HERO_LAYER_SEGMENTATION"
    return "E01_2_FAIL_CANVA_LAYER_TARGET"

