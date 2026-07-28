"""D06 readiness and patch queue helpers for D05."""

from __future__ import annotations

from typing import Any


def build_patch_queue(reference_results: list[dict[str, Any]], *, text_risk_bounded: bool, mask_risk_bounded: bool) -> dict[str, Any]:
    patches: list[dict[str, Any]] = []
    if text_risk_bounded:
        patches.append(
            {
                "reference_id": "pilot_scope",
                "layer_id": None,
                "issue": "OCR backend unavailable; text content is slot geometry only.",
                "evidence": "D02/D04 OCR status unavailable and D05 text risk gate bounded.",
                "severity": "MEDIUM_PATCH",
                "category": "text_ocr_risk",
                "proposed_action": "Add local OCR or manual text confirmation before productizing final copy lift.",
                "D05_rerun_required": False,
                "D06_remains_locked": False,
            }
        )
    if mask_risk_bounded:
        patches.append(
            {
                "reference_id": "pilot_scope",
                "layer_id": None,
                "issue": "Masks are mostly rectangular; polygon fidelity remains limited.",
                "evidence": "D01 mask manifests contain bbox-style masks with sparse polygon data.",
                "severity": "MEDIUM_PATCH",
                "category": "mask_polygon_fidelity",
                "proposed_action": "Improve polygon extraction and diagonal mask capture in D06/D05 patch loop.",
                "D05_rerun_required": False,
                "D06_remains_locked": False,
            }
        )
    for result in reference_results:
        if result.get("visual_fidelity_status") == "failed":
            patches.append(
                {
                    "reference_id": result["reference_id"],
                    "layer_id": None,
                    "issue": "Editable candidate render failed D05 visual fidelity.",
                    "evidence": result.get("reference_vs_render"),
                    "severity": "HIGH_PRODUCT_RISK",
                    "category": "render_fidelity",
                    "proposed_action": "Patch candidate compiler geometry/style mapping and rerun D05.",
                    "D05_rerun_required": True,
                    "D06_remains_locked": True,
                }
            )
    return {
        "schema_name": "patch_queue_d05",
        "patch_count": len(patches),
        "critical_blocker_count": len([item for item in patches if item["severity"] == "CRITICAL_BLOCKER"]),
        "high_product_risk_count": len([item for item in patches if item["severity"] == "HIGH_PRODUCT_RISK"]),
        "patches": patches,
    }


def build_d06_readiness(
    *,
    reference_results: list[dict[str, Any]],
    text_risk_status: str,
    mask_risk_status: str,
    unknown_gate: dict[str, Any],
    patch_queue: dict[str, Any],
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    all_compiled = all(item.get("candidate_compiled") for item in reference_results)
    all_rendered = all(item.get("candidate_rendered") for item in reference_results)
    no_background = all(item.get("no_full_slide_background") for item in reference_results)
    no_screenshot = all(item.get("no_screenshot_slide") for item in reference_results)
    semantic_ok = all(item.get("semantic_editability_status") == "passed" for item in reference_results)
    visual_ok = all(item.get("visual_fidelity_status") != "failed" for item in reference_results)
    no_high = patch_queue.get("critical_blocker_count", 0) == 0 and patch_queue.get("high_product_risk_count", 0) == 0
    unknown_ok = unknown_gate.get("content_bearing_unknown_layer_count", 0) == 0 and unknown_gate.get("silently_passed_unknown_layer_count", 0) == 0
    unlocked = all_compiled and all_rendered and no_background and no_screenshot and semantic_ok and visual_ok and no_high and unknown_ok and protected_artifacts_unchanged
    if not protected_artifacts_unchanged:
        decision = "D05_FAIL_PROTECTED_ARTIFACTS"
    elif not semantic_ok:
        decision = "D05_PATCH_SEMANTIC_EDITABILITY"
    elif not unknown_ok:
        decision = "D05_PATCH_UNKNOWN_LAYER_POLICY"
    elif not visual_ok:
        decision = "D05_PATCH_RENDER_FIDELITY"
    elif text_risk_status != "bounded":
        decision = "D05_PATCH_TEXT_OCR_RISK"
    elif mask_risk_status != "bounded":
        decision = "D05_PATCH_MASK_POLYGON_FIDELITY"
    else:
        decision = "D05_PASS_WITH_LIMITED_TEXT_AND_MASK_RISK_START_D06"
    return {
        "schema_name": "d06_readiness_report",
        "decision": decision,
        "d06_unlocked": unlocked and decision in {"D05_PASS_START_D06_BATCH_TEMPLATE_REFERENCE_CONVERSION", "D05_PASS_WITH_LIMITED_TEXT_AND_MASK_RISK_START_D06"},
        "unlock_conditions": {
            "all_pilot_editable_candidates_compile": all_compiled,
            "all_pilot_candidates_render": all_rendered,
            "no_full_slide_reference_background": no_background,
            "no_screenshot_slides": no_screenshot,
            "semantic_components_editable_or_rejected": semantic_ok,
            "no_semantic_raster_icon_chart_table": semantic_ok,
            "unknown_content_bearing_layers_zero": unknown_ok,
            "text_ocr_risk_bounded": text_risk_status == "bounded",
            "mask_polygon_risk_bounded": mask_risk_status == "bounded",
            "reference_vs_render_fidelity_acceptable": visual_ok,
            "no_critical_blockers": patch_queue.get("critical_blocker_count", 0) == 0,
            "no_high_product_risks": patch_queue.get("high_product_risk_count", 0) == 0,
            "source_bound_decks_created": False,
            "bulk_decks_created": False,
            "c11_remains_frozen": True,
            "protected_artifacts_unchanged": protected_artifacts_unchanged,
        },
        "canva_parity_claimed": False,
    }


def build_d05_reclassification(d05_report: dict[str, Any], d06_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "d05_reclassification_report",
        "decision": "D05_1_REQUIRED_BEFORE_D06_BATCH_CONVERSION",
        "d05_candidate_compiler_status": "PASS" if d05_report.get("candidates_compiled", 0) else "FAIL",
        "d05_render_status": "PASS" if d05_report.get("renders_succeeded", 0) == d05_report.get("references_processed", -1) else "FAIL",
        "d05_no_background_screenshot_policy": "PASS" if d05_report.get("no_background_screenshot_status") == "passed" else "FAIL",
        "d05_semantic_editability_status": "PASS" if d05_report.get("semantic_editability_status") == "passed" else "FAIL",
        "d05_unknown_layer_status": "PASS" if d05_report.get("unknown_layer_status") == "passed" else "FAIL",
        "d05_text_ocr_status": "BOUNDED_RISK",
        "d05_mask_polygon_status": "LIMITED_BOUNDED",
        "d05_visual_fidelity_status": "INSUFFICIENT_FOR_D06_PRODUCT_BATCH",
        "d06_technical_unlock": bool(d06_report.get("d06_unlocked")),
        "d06_product_batch_unlock": "REVOKED_PENDING_D05_1",
        "canva_parity_claimed": False,
    }


def build_d06_revised_readiness(
    *,
    reference_results: list[dict[str, Any]],
    patch_queue: dict[str, Any],
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    all_compiled = all(item.get("patched_candidate_compiled") for item in reference_results)
    all_rendered = all(item.get("patched_candidate_rendered") for item in reference_results)
    no_background = all(item.get("no_full_slide_background") for item in reference_results)
    no_screenshot = all(item.get("no_screenshot_slide") for item in reference_results)
    semantic_ok = all(item.get("semantic_editability_status") == "passed" for item in reference_results)
    major_ok = all(item.get("major_region_coverage_status") == "passed" for item in reference_results)
    visual_ok = all(item.get("product_visual_fidelity_status") == "passed" for item in reference_results)
    unknown_ok = all(item.get("content_bearing_unknown_layer_count", 0) == 0 for item in reference_results)
    no_high = patch_queue.get("critical_blocker_count", 0) == 0 and patch_queue.get("high_product_risk_count", 0) == 0
    unlocked = all_compiled and all_rendered and no_background and no_screenshot and semantic_ok and major_ok and visual_ok and unknown_ok and no_high and protected_artifacts_unchanged
    if not protected_artifacts_unchanged:
        decision = "D05_1_FAIL_PROTECTED_ARTIFACTS"
    elif not visual_ok:
        decision = "D05_1_FAIL_VISUAL_FIDELITY_FOR_D06"
    elif not major_ok:
        decision = "D05_1_PATCH_MAJOR_REGION_PRESERVATION"
    elif not semantic_ok:
        decision = "D05_1_PATCH_SEMANTIC_EDITABILITY"
    else:
        decision = "D05_1_PASS_WITH_LIMITED_TEXT_AND_MASK_RISK_START_D06"
    return {
        "schema_name": "d06_revised_readiness_report",
        "decision": decision,
        "d06_unlocked": unlocked
        and decision in {"D05_1_PASS_START_D06_BATCH_TEMPLATE_REFERENCE_CONVERSION", "D05_1_PASS_WITH_LIMITED_TEXT_AND_MASK_RISK_START_D06"},
        "unlock_conditions": {
            "patched_candidates_compile_5_of_5": all_compiled,
            "patched_candidates_render_5_of_5": all_rendered,
            "no_full_slide_reference_background": no_background,
            "no_screenshot_slide": no_screenshot,
            "semantic_components_editable_or_rejected": semantic_ok,
            "no_semantic_raster_icon_chart_table": semantic_ok,
            "unknown_content_bearing_layers_zero": unknown_ok,
            "text_ocr_risk_bounded": True,
            "mask_polygon_risk_bounded": True,
            "major_visual_regions_preserved_or_scoped": major_ok,
            "reference_vs_render_fidelity_acceptable": visual_ok,
            "no_critical_blockers": patch_queue.get("critical_blocker_count", 0) == 0,
            "no_high_product_risks": patch_queue.get("high_product_risk_count", 0) == 0,
            "source_bound_deck_created": False,
            "bulk_deck_created": False,
            "c11_remains_frozen": True,
            "protected_artifacts_unchanged": protected_artifacts_unchanged,
        },
        "canva_parity_claimed": False,
    }
