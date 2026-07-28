"""D06.1 reclassification and D07 readiness helpers."""

from __future__ import annotations

from typing import Any


def build_d06_reclassification(d06_report: dict[str, Any], d07_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "d06_reclassification_report",
        "decision": "D06_RECLASSIFIED_STRUCTURAL_PASS_VISUAL_PATCH_REQUIRED",
        "d06_structural_batch_status": "PASS" if d06_report.get("references_processed") == 16 else "FAIL",
        "d06_isolated_compile_status": "PASS" if d06_report.get("candidates_compiled") == 16 else "FAIL",
        "d06_isolated_render_status": "PASS" if d06_report.get("candidates_rendered") == 16 else "FAIL",
        "d06_semantic_editability_status": "PASS",
        "d06_text_ocr_status": "BOUNDED_RISK",
        "d06_mask_polygon_status": "BOUNDED_RISK",
        "d06_automated_visual_report_status": "PASS",
        "d06_product_visual_fidelity_status": "INSUFFICIENT_FOR_D07_SOURCE_BOUND_DECK",
        "d07_technical_unlock": bool(d07_report.get("d07_unlocked")),
        "d07_product_unlock": "REVOKED_PENDING_D06_1",
        "d06_1_required": True,
        "canva_parity_claimed": False,
    }


def build_d07_revised_readiness(
    reference_results: list[dict[str, Any]],
    patch_queue: dict[str, Any],
    *,
    candidate_pack_exists: bool,
    routing_manifest_exists: bool,
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    processed = len(reference_results) == 16
    compiled = all(item.get("d06_1_candidate_compiled") for item in reference_results)
    rendered = all(item.get("d06_1_candidate_rendered") for item in reference_results)
    visual_ok = all(item.get("visual_fidelity_v2_status") == "passed" for item in reference_results)
    identity_ok = all(item.get("archetype_identity_status") == "passed" for item in reference_results)
    clutter_ok = all(item.get("placeholder_clutter_status") == "passed" for item in reference_results)
    major_ok = all(item.get("major_region_coverage_status") == "passed" for item in reference_results)
    no_background = all(item.get("no_full_slide_background") for item in reference_results)
    no_screenshot = all(item.get("no_screenshot_slide") for item in reference_results)
    semantic_ok = all(item.get("semantic_editability_status") == "passed" and item.get("semantic_raster_count", 0) == 0 for item in reference_results)
    unknown_ok = all(item.get("unknown_content_bearing_layer_count", 0) == 0 for item in reference_results)
    text_bounded = all(item.get("text_ocr_risk_status") == "bounded" for item in reference_results)
    mask_bounded = all(item.get("mask_polygon_risk_status") == "bounded" for item in reference_results)
    pack_or_routing = candidate_pack_exists or routing_manifest_exists
    no_high = patch_queue.get("critical_blocker_count", 0) == 0 and patch_queue.get("high_product_risk_count", 0) == 0
    unlocked = (
        processed
        and compiled
        and rendered
        and visual_ok
        and identity_ok
        and clutter_ok
        and major_ok
        and no_background
        and no_screenshot
        and semantic_ok
        and unknown_ok
        and text_bounded
        and mask_bounded
        and pack_or_routing
        and no_high
        and protected_artifacts_unchanged
    )
    if not protected_artifacts_unchanged:
        decision = "D06_1_FAIL_PROTECTED_ARTIFACTS"
    elif not processed or not compiled or not rendered:
        decision = "D06_1_FAIL_D07_PRODUCT_READINESS"
    elif not visual_ok:
        decision = "D06_1_PATCH_EXPANSION_VISUAL_FIDELITY"
    elif not clutter_ok:
        decision = "D06_1_PATCH_PLACEHOLDER_CLUTTER"
    elif not identity_ok or not major_ok:
        decision = "D06_1_PATCH_ARCHETYPE_IDENTITY"
    elif not pack_or_routing:
        decision = "D06_1_PATCH_CANDIDATE_PACK"
    else:
        decision = "D06_1_PASS_WITH_LIMITED_TEXT_AND_MASK_RISK_START_D07"
    return {
        "schema_name": "d07_revised_readiness_report",
        "decision": decision,
        "d07_unlocked": unlocked and decision in {"D06_1_PASS_START_D07_SOURCE_BOUND_SMALL_DECK", "D06_1_PASS_WITH_LIMITED_TEXT_AND_MASK_RISK_START_D07"},
        "unlock_conditions": {
            "patched_references_compile_16_of_16": compiled,
            "patched_references_render_16_of_16": rendered,
            "reference_vs_render_contact_sheets_acceptable": visual_ok,
            "no_generic_white_block_debug_regression": visual_ok,
            "placeholder_clutter_bounded": clutter_ok,
            "archetype_identity_passes_every_reference": identity_ok,
            "major_region_coverage_passes_every_reference": major_ok,
            "no_full_slide_reference_background": no_background,
            "no_screenshot_slide": no_screenshot,
            "semantic_components_editable_or_rejected": semantic_ok,
            "semantic_raster_icon_chart_table_final_use_zero": semantic_ok,
            "unknown_content_bearing_layers_zero": unknown_ok,
            "text_ocr_risk_bounded": text_bounded,
            "mask_polygon_risk_bounded": mask_bounded,
            "candidate_pack_or_routing_manifest_exists": pack_or_routing,
            "no_critical_blockers": patch_queue.get("critical_blocker_count", 0) == 0,
            "no_high_product_risks": patch_queue.get("high_product_risk_count", 0) == 0,
            "source_bound_deck_created": False,
            "bulk_deck_created": False,
            "c11_remains_frozen": True,
            "protected_artifacts_unchanged": protected_artifacts_unchanged,
        },
        "canva_parity_claimed": False,
    }
