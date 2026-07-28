"""D08 readiness helpers for D07 source-bound proof decks."""

from __future__ import annotations

from typing import Any


def build_d08_readiness(
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
    full_slide_background_violation: bool,
    screenshot_slide_violation: bool,
    semantic_raster_count: int,
    unknown_content_bearing_layer_count: int,
    visual_product_gate_passed: bool,
    critical_blocker_count: int,
    high_product_risk_count: int,
    large_deck_created: bool,
    bulk_deck_created: bool,
    c11_started: bool,
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    slide_count_ok = 12 <= slide_count <= 16
    all_slides_render = rendered_slide_count == slide_count and slide_count_ok
    unlocked = (
        deck_exists
        and slide_count_ok
        and all_slides_render
        and source_binding_passed
        and citation_binding_passed
        and template_slot_binding_passed
        and placeholder_leakage_count == 0
        and fixture_text_leakage_count == 0
        and text_overflow_count == 0
        and not full_slide_background_violation
        and not screenshot_slide_violation
        and semantic_raster_count == 0
        and unknown_content_bearing_layer_count == 0
        and visual_product_gate_passed
        and critical_blocker_count == 0
        and high_product_risk_count == 0
        and not large_deck_created
        and not bulk_deck_created
        and not c11_started
        and protected_artifacts_unchanged
    )
    if not protected_artifacts_unchanged:
        decision = "D07_FAIL_PROTECTED_ARTIFACTS"
    elif not source_binding_passed:
        decision = "D07_PATCH_SOURCE_BINDING"
    elif not template_slot_binding_passed:
        decision = "D07_PATCH_TEMPLATE_SLOT_BINDING"
    elif placeholder_leakage_count:
        decision = "D07_PATCH_PLACEHOLDER_LEAKAGE"
    elif text_overflow_count:
        decision = "D07_PATCH_TEXT_OVERFLOW"
    elif not visual_product_gate_passed or critical_blocker_count or high_product_risk_count:
        decision = "D07_PATCH_VISUAL_PRODUCT_QUALITY"
    elif semantic_raster_count:
        decision = "D07_PATCH_CHART_TABLE_BINDING"
    else:
        decision = "D07_PASS_WITH_LIMITED_TEXT_AND_MASK_RISK_START_D08"
    return {
        "schema_name": "d07_d08_readiness_report",
        "decision": decision,
        "d08_unlocked": unlocked and decision in {"D07_PASS_START_D08_34_SLIDE_SCALEOUT_WITH_MAGIC_LAYER_PACK", "D07_PASS_WITH_LIMITED_TEXT_AND_MASK_RISK_START_D08"},
        "unlock_conditions": {
            "d07_deck_exists": deck_exists,
            "slide_count_12_to_16": slide_count_ok,
            "all_slides_render": all_slides_render,
            "source_binding_passed": source_binding_passed,
            "citation_binding_passed": citation_binding_passed,
            "template_slot_binding_passed": template_slot_binding_passed,
            "placeholder_leakage_zero": placeholder_leakage_count == 0,
            "fixture_text_leakage_zero": fixture_text_leakage_count == 0,
            "text_overflow_zero": text_overflow_count == 0,
            "no_full_slide_reference_background": not full_slide_background_violation,
            "no_screenshot_slide": not screenshot_slide_violation,
            "semantic_components_editable_or_rejected": semantic_raster_count == 0,
            "semantic_raster_icon_chart_table_final_use_zero": semantic_raster_count == 0,
            "unknown_content_bearing_layers_zero": unknown_content_bearing_layer_count == 0,
            "visual_product_gate_passed": visual_product_gate_passed,
            "no_critical_blockers": critical_blocker_count == 0,
            "no_high_product_risks": high_product_risk_count == 0,
            "large_deck_created": large_deck_created,
            "bulk_deck_created": bulk_deck_created,
            "c11_remains_frozen": not c11_started,
            "protected_artifacts_unchanged": protected_artifacts_unchanged,
        },
        "canva_parity_claimed": False,
    }
