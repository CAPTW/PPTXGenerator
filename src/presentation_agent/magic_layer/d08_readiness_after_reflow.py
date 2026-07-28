"""D08 readiness gate after D07.1 layout geometry reflow."""

from __future__ import annotations

from typing import Any


def build_d08_revised_readiness_after_reflow(
    *,
    deck_exists: bool,
    slide_count: int,
    rendered_slide_count: int,
    source_binding_passed: bool,
    citation_binding_passed: bool,
    template_slot_binding_passed: bool,
    placeholder_leakage_count: int,
    fixture_text_leakage_count: int,
    text_overflow_count: int,
    semantic_raster_count: int,
    full_slide_background_violation: bool,
    screenshot_slide_violation: bool,
    geometry_gate_passed: bool,
    overlap_gate_passed: bool,
    source_footer_geometry_gate_passed: bool,
    z_order_gate_passed: bool,
    visual_product_gate_passed: bool,
    critical_blocker_count: int,
    high_product_risk_count: int,
    large_deck_created: bool,
    bulk_deck_created: bool,
    c11_started: bool,
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    slide_count_ok = 12 <= slide_count <= 16
    all_rendered = rendered_slide_count == slide_count and slide_count_ok
    unlocked = (
        deck_exists
        and slide_count_ok
        and all_rendered
        and source_binding_passed
        and citation_binding_passed
        and template_slot_binding_passed
        and placeholder_leakage_count == 0
        and fixture_text_leakage_count == 0
        and text_overflow_count == 0
        and semantic_raster_count == 0
        and not full_slide_background_violation
        and not screenshot_slide_violation
        and geometry_gate_passed
        and overlap_gate_passed
        and source_footer_geometry_gate_passed
        and z_order_gate_passed
        and visual_product_gate_passed
        and critical_blocker_count == 0
        and high_product_risk_count == 0
        and not large_deck_created
        and not bulk_deck_created
        and not c11_started
        and protected_artifacts_unchanged
    )
    if not protected_artifacts_unchanged:
        decision = "D07_1_FAIL_PROTECTED_ARTIFACTS"
    elif not geometry_gate_passed or not overlap_gate_passed:
        decision = "D07_1_PATCH_LAYOUT_GEOMETRY"
    elif text_overflow_count:
        decision = "D07_1_PATCH_TEXT_CAPACITY"
    elif not source_footer_geometry_gate_passed:
        decision = "D07_1_PATCH_SOURCE_FOOTER_GEOMETRY"
    elif not z_order_gate_passed:
        decision = "D07_1_PATCH_Z_ORDER"
    elif not visual_product_gate_passed or high_product_risk_count:
        decision = "D07_1_PATCH_VISUAL_PRODUCT_QUALITY"
    elif not all_rendered or not deck_exists:
        decision = "D07_1_FAIL_D08_PRODUCT_READINESS"
    else:
        decision = "D07_1_PASS_WITH_LIMITED_TEXT_AND_MASK_RISK_START_D08"
    return {
        "schema_name": "d08_revised_readiness_report",
        "decision": decision,
        "d08_unlocked": unlocked and decision in {"D07_1_PASS_START_D08_34_SLIDE_SCALEOUT_WITH_MAGIC_LAYER_PACK", "D07_1_PASS_WITH_LIMITED_TEXT_AND_MASK_RISK_START_D08"},
        "unlock_conditions": {
            "d07_1_reflowed_deck_exists": deck_exists,
            "slide_count_12_to_16": slide_count_ok,
            "all_slides_render": all_rendered,
            "source_binding_passed": source_binding_passed,
            "citation_binding_passed": citation_binding_passed,
            "template_slot_binding_passed": template_slot_binding_passed,
            "placeholder_leakage_zero": placeholder_leakage_count == 0,
            "fixture_text_leakage_zero": fixture_text_leakage_count == 0,
            "text_overflow_zero": text_overflow_count == 0,
            "semantic_raster_icon_chart_table_final_use_zero": semantic_raster_count == 0,
            "no_full_slide_reference_background": not full_slide_background_violation,
            "no_screenshot_slide": not screenshot_slide_violation,
            "geometry_gate_passes": geometry_gate_passed,
            "overlap_gate_passes": overlap_gate_passed,
            "source_footer_geometry_gate_passes": source_footer_geometry_gate_passed,
            "z_order_gate_passes": z_order_gate_passed,
            "visual_product_gate_passes": visual_product_gate_passed,
            "no_critical_blockers": critical_blocker_count == 0,
            "no_high_product_risks": high_product_risk_count == 0,
            "large_deck_created": large_deck_created,
            "bulk_deck_created": bulk_deck_created,
            "c11_remains_frozen": not c11_started,
            "protected_artifacts_unchanged": protected_artifacts_unchanged,
        },
        "canva_parity_claimed": False,
    }
