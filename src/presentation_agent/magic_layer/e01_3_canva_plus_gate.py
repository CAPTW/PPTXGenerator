"""Strict E01.3 semantic icon vector gate."""

from __future__ import annotations

from typing import Any


def evaluate_e01_3_canva_plus_gate(candidate: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    high_risks: list[str] = []
    for key, failure in {
        "candidate_renders": "candidate_render_missing",
        "no_full_slide_reference_background": "full_slide_reference_background",
        "no_screenshot_slide": "screenshot_slide",
        "semantic_icon_roles_resolved": "semantic_icon_roles_unresolved",
        "generated_svg_policy_pass": "generated_svg_policy_failed",
        "generated_svg_insertion_pass": "generated_svg_insertion_failed",
        "checklist_icon_roles_pass": "checklist_icon_roles_failed",
        "bottom_action_icon_roles_pass": "bottom_action_icon_roles_failed",
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
    if candidate.get("visual_no_regression_from_e01_2") is not True:
        blockers.append("visual_regression_from_e01_2")
    if candidate.get("final_layer_segmentation_target_met") is not True:
        high_risks.append("layer_segmentation_fidelity_still_below_final_target")

    if blockers:
        decision = _patch_decision(blockers)
    elif high_risks:
        decision = "E01_3_PASS_START_E01_4_LAYER_SEGMENTATION_POLISH"
    else:
        decision = "E01_3_PASS_UNLOCK_E02_CONTROLLED_BATCH_CONVERSION"
    return {
        "schema_name": "canva_plus_gate_report_e01_3",
        "status": "passed" if not blockers else "failed",
        "decision": decision,
        "e02_unlocked": decision == "E01_3_PASS_UNLOCK_E02_CONTROLLED_BATCH_CONVERSION",
        "e01_4_unlocked": decision == "E01_3_PASS_START_E01_4_LAYER_SEGMENTATION_POLISH",
        "blockers": blockers,
        "high_product_risks": high_risks,
        "canva_parity_claimed": decision == "E01_3_PASS_UNLOCK_E02_CONTROLLED_BATCH_CONVERSION",
    }


def _patch_decision(blockers: list[str]) -> str:
    if "generated_svg_policy_failed" in blockers:
        return "E01_3_PATCH_GENERATED_SVG_POLICY"
    if "generated_svg_insertion_failed" in blockers:
        return "E01_3_PATCH_SVG_INSERTION"
    if "checklist_icon_roles_failed" in blockers:
        return "E01_3_PATCH_CHECKLIST_ICON_ROLES"
    if "bottom_action_icon_roles_failed" in blockers:
        return "E01_3_PATCH_BOTTOM_ACTION_ICON_ROLES"
    if "semantic_icon_roles_unresolved" in blockers or "semantic_raster_violations" in blockers:
        return "E01_3_FAIL_SEMANTIC_ICON_VECTOR_GATE"
    return "E01_3_FAIL_CANVA_LAYER_TARGET"

