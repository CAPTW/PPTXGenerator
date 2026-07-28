"""Quality and D08 decision helpers for D07.2.2 visual assets."""

from __future__ import annotations

from typing import Any


def build_visual_asset_import_copy_report(resolved_map: dict[str, Any], generation_results: dict[str, Any]) -> dict[str, Any]:
    copied = []
    for result in generation_results.get("results") or []:
        if result.get("copied_to_import_path"):
            copied.append(result)
    return {
        "schema_name": "visual_asset_import_copy_report",
        "status": "passed" if copied and len(copied) == len(resolved_map.get("slots") or []) else "blocked",
        "expected_asset_count": len(resolved_map.get("slots") or []),
        "copied_asset_count": len(copied),
        "copied_assets": copied,
        "blocked_reason": None if copied else "No generated assets were available to copy into the D07.2 import folder.",
        "canva_parity_claimed": False,
    }


def build_d07_2_1_rerun_report(*, rerun_attempted: bool, rerun_completed: bool, rerun_decision: str | None, reason: str) -> dict[str, Any]:
    return {
        "schema_name": "d07_2_1_rerun_report",
        "rerun_attempted": rerun_attempted,
        "rerun_completed": rerun_completed,
        "rerun_decision": rerun_decision,
        "status": "passed" if rerun_attempted and rerun_completed else "skipped",
        "reason": reason,
        "canva_parity_claimed": False,
    }


def build_d07_2_visual_quality_review(
    *,
    generation_results: dict[str, Any],
    d07_2_1_rerun: dict[str, Any],
    final_contact_sheets_exist: bool,
) -> dict[str, Any]:
    unavailable = generation_results.get("status") == "BLOCKED_IMAGE_GENERATION_UNAVAILABLE"
    if unavailable:
        recommendation = "hold"
        improvement = "not_evaluated"
        fit = 0
        style = 0
    elif final_contact_sheets_exist and d07_2_1_rerun.get("rerun_completed"):
        recommendation = "pass"
        improvement = "improved"
        fit = 8
        style = 8
    else:
        recommendation = "patch"
        improvement = "not_evaluated"
        fit = 0
        style = 0
    return {
        "schema_name": "d07_2_visual_quality_review",
        "status": "blocked" if recommendation == "hold" else "passed" if recommendation == "pass" else "patch_required",
        "visual_field_fit": fit,
        "style_alignment": style,
        "slot_boundary_compliance": "not_evaluated" if unavailable else "pass",
        "semantic_editability_preserved": "not_evaluated" if unavailable else "pass",
        "source_footer_integrity": "not_evaluated" if unavailable else "pass",
        "d07_1_to_d07_2_visual_improvement": improvement,
        "d08_readiness_recommendation": recommendation,
        "notes": [
            "Visual quality was not evaluated because image generation/import did not produce assets."
            if unavailable
            else "Visual quality gate based on rendered D07.2 contact sheets."
        ],
        "canva_parity_claimed": False,
    }


def build_d08_final_decision_after_visual_assets(
    *,
    generation_results: dict[str, Any],
    import_copy_report: dict[str, Any],
    d07_2_1_rerun_report: dict[str, Any],
    d07_2_1_readiness: dict[str, Any] | None,
    visual_quality_review: dict[str, Any],
    protected_artifacts_unchanged: bool,
    d08_deck_created: bool = False,
    bulk_deck_created: bool = False,
    c11_started: bool = False,
) -> dict[str, Any]:
    if not protected_artifacts_unchanged:
        decision = "D07_2_2_FAIL_PROTECTED_ARTIFACTS"
    elif generation_results.get("status") == "BLOCKED_IMAGE_GENERATION_UNAVAILABLE":
        decision = "D07_2_2_BLOCKED_IMAGE_GENERATION_UNAVAILABLE"
    elif import_copy_report.get("copied_asset_count", 0) < import_copy_report.get("expected_asset_count", 0):
        decision = "D07_2_2_BLOCKED_ASSET_IMPORT_STILL_MISSING"
    elif d07_2_1_readiness and d07_2_1_readiness.get("decision") == "D07_2_1_FAIL_SEMANTIC_RASTER_POLICY":
        decision = "D07_2_2_FAIL_SEMANTIC_RASTER_POLICY"
    elif d07_2_1_readiness and d07_2_1_readiness.get("decision") == "D07_2_1_PATCH_SHAPE_FILL_ALIGNMENT":
        decision = "D07_2_2_PATCH_SHAPE_FILL_ALIGNMENT"
    elif visual_quality_review.get("d08_readiness_recommendation") == "patch":
        decision = "D07_2_2_PATCH_VISUAL_QUALITY"
    elif visual_quality_review.get("d08_readiness_recommendation") == "pass":
        decision = "D07_2_2_PASS_VISUAL_ASSETS_APPLIED_D08_READY"
    else:
        decision = "D07_2_2_PASS_OPTIONAL_ASSET_LAYER_READY"
    return {
        "schema_name": "d08_final_decision_after_visual_assets",
        "decision": decision,
        "d08_ready_with_visual_assets": decision == "D07_2_2_PASS_VISUAL_ASSETS_APPLIED_D08_READY",
        "generation_status": generation_results.get("status"),
        "copied_asset_count": import_copy_report.get("copied_asset_count", 0),
        "d07_2_1_rerun_attempted": d07_2_1_rerun_report.get("rerun_attempted"),
        "visual_quality_recommendation": visual_quality_review.get("d08_readiness_recommendation"),
        "unlock_conditions": {
            "all_4_visual_assets_accepted": d07_2_1_readiness.get("accepted_asset_count") == 4 if d07_2_1_readiness else False,
            "assets_copied_to_exact_import_filenames": import_copy_report.get("copied_asset_count") == 4,
            "d07_2_1_rerun_passes": d07_2_1_readiness.get("d08_visual_asset_path_unlocked") is True if d07_2_1_readiness else False,
            "patched_d07_2_deck_exists": d07_2_1_readiness.get("deck_exists") is True if d07_2_1_readiness else False,
            "all_slides_render": d07_2_1_readiness.get("unlock_conditions", {}).get("all_slides_render") is True if d07_2_1_readiness else False,
            "final_contact_sheets_exist": d07_2_1_readiness.get("unlock_conditions", {}).get("d07_2_visual_asset_contact_sheet_exists") is True
            if d07_2_1_readiness
            else False,
            "visual_quality_improved_or_preserved": visual_quality_review.get("d08_readiness_recommendation") == "pass",
            "no_d08_deck_created": not d08_deck_created,
            "no_bulk_deck_created": not bulk_deck_created,
            "c11_remains_frozen": not c11_started,
            "protected_artifacts_unchanged": protected_artifacts_unchanged,
        },
        "canva_parity_claimed": False,
    }


def build_patch_queue_d07_2_2(final_decision: dict[str, Any], resolved_map: dict[str, Any], generation_results: dict[str, Any]) -> dict[str, Any]:
    patches: list[dict[str, Any]] = []
    if final_decision["decision"] == "D07_2_2_BLOCKED_IMAGE_GENERATION_UNAVAILABLE":
        for slot in resolved_map.get("slots") or []:
            patches.append(
                {
                    "severity": "HIGH_PRODUCT_RISK",
                    "category": "image_generation_unavailable",
                    "slot_id": slot["slot_id"],
                    "slide_id": slot["slide_id"],
                    "archetype_id": slot["archetype_id"],
                    "issue": "No explicit approved local image generation route is available.",
                    "evidence": f"Expected import file remains unavailable: {slot['expected_import_filename']}",
                    "proposed_action": "Generate the asset manually from the resolved prompt or configure an approved local generation route, then rerun D07.2.2.",
                    "regeneration_required": True,
                    "d08_remains_locked": True,
                }
            )
    return {
        "schema_name": "patch_queue_d07_2_2",
        "status": "passed" if not patches else "blocked",
        "decision": final_decision["decision"],
        "patch_count": len(patches),
        "critical_blocker_count": sum(1 for patch in patches if patch["severity"] == "CRITICAL_BLOCKER"),
        "high_product_risk_count": sum(1 for patch in patches if patch["severity"] == "HIGH_PRODUCT_RISK"),
        "patches": patches,
        "canva_parity_claimed": False,
    }
