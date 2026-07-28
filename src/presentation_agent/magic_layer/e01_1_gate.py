"""E01.1 semantic component lift gate."""

from __future__ import annotations

from typing import Any


PASS_DECISION = "E01_1_PASS_START_E01_2_RENDER_FIDELITY_PATCH"


def evaluate_e01_1_gate(candidate: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    high_risks: list[str] = []

    if candidate.get("candidate_renders") is not True:
        blockers.append("candidate_render_missing")
    if candidate.get("full_slide_reference_background") is True:
        blockers.append("full_slide_reference_background")
    if candidate.get("screenshot_slide") is True:
        blockers.append("screenshot_slide")
    if int(candidate.get("unknown_content_bearing_layer_count", 0)) > 0:
        blockers.append("unknown_content_bearing_layers")
    if int(candidate.get("semantic_raster_violation_count", 0)) > 0:
        blockers.append("semantic_raster_violations")
    if candidate.get("checklist_component_reconstructed") is not True:
        blockers.append("checklist_component_not_reconstructed")
    if candidate.get("bottom_action_bar_reconstructed") is not True:
        blockers.append("bottom_action_bar_not_reconstructed")
    if candidate.get("source_footer_reconstructed") is not True:
        blockers.append("source_footer_not_reconstructed")
    if candidate.get("semantic_icons_vector") is not True:
        blockers.append("semantic_icons_not_vector")
    if candidate.get("text_regions_editable") is not True:
        blockers.append("text_regions_not_editable")
    if int(candidate.get("text_overflow_count", 0)) > 0:
        blockers.append("text_overflow")
    if int(candidate.get("severe_layout_overlap_count", 0)) > 0:
        blockers.append("severe_layout_overlap")
    if candidate.get("visual_fidelity_improved_over_e01") is not True:
        high_risks.append("visual_fidelity_not_improved_over_e01")
    if candidate.get("major_reference_composition_preserved") is not True:
        high_risks.append("major_reference_composition_not_preserved")

    decision = _decision_for(blockers, high_risks)
    return {
        "schema_name": "canva_plus_gate_report_e01_1",
        "status": "passed" if decision == PASS_DECISION else "failed",
        "decision": decision,
        "e01_2_unlocked": decision == PASS_DECISION,
        "e02_unlocked": False,
        "blockers": blockers,
        "high_product_risks": high_risks,
        "canva_parity_claimed": False,
        "canva_parity_note": "E01.1 may unlock E01.2 polish only; final Canva parity is reserved for the final strict gate.",
    }


def _decision_for(blockers: list[str], high_risks: list[str]) -> str:
    if "semantic_raster_violations" in blockers or "text_regions_not_editable" in blockers or "semantic_icons_not_vector" in blockers:
        return "E01_1_FAIL_SEMANTIC_EDITABILITY"
    if "checklist_component_not_reconstructed" in blockers:
        return "E01_1_PATCH_CHECKLIST_COMPONENT_RECONSTRUCTION"
    if "bottom_action_bar_not_reconstructed" in blockers:
        return "E01_1_PATCH_BOTTOM_ACTION_BAR_RECONSTRUCTION"
    if "text_overflow" in blockers or "severe_layout_overlap" in blockers:
        return "E01_1_PATCH_LAYOUT_REFLOW"
    if blockers:
        return "E01_1_PATCH_SEMANTIC_COMPONENT_LIFT"
    if high_risks:
        return "E01_1_PATCH_LAYOUT_REFLOW"
    return PASS_DECISION

