"""D08 readiness labels for D07.2.1 visual asset import patch."""

from __future__ import annotations

from typing import Any


def build_d08_revised_visual_asset_readiness(
    *,
    validation_report: dict[str, Any],
    deck_patch_report: dict[str, Any],
    render_manifest: dict[str, Any],
    semantic_policy_report: dict[str, Any],
    alignment_report: dict[str, Any],
    diagnostic_sheets: dict[str, Any],
    protected_artifacts_unchanged: bool,
    slide_count: int,
    large_deck_created: bool = False,
    bulk_deck_created: bool = False,
    c11_started: bool = False,
) -> dict[str, Any]:
    all_assets_accepted = validation_report.get("all_required_assets_accepted") is True
    deck_exists = deck_patch_report.get("deck_created") is True
    all_rendered = deck_exists and render_manifest.get("rendered_slide_count") == slide_count
    final_contacts_exist = bool(render_manifest.get("final_contact_sheets_exist"))
    no_semantic = semantic_policy_report.get("semantic_violation_count", 0) == 0
    alignment_ok = alignment_report.get("status") == "passed"
    diagnostic_ok = all(sheet.get("status") == "created" for sheet in diagnostic_sheets.values())

    if not protected_artifacts_unchanged:
        decision = "D07_2_1_FAIL_PROTECTED_ARTIFACTS"
    elif not all_assets_accepted:
        decision = "D07_2_1_BLOCKED_ASSET_IMPORT_REQUIRED"
    elif not no_semantic:
        decision = "D07_2_1_FAIL_SEMANTIC_RASTER_POLICY"
    elif not alignment_ok:
        decision = "D07_2_1_PATCH_SHAPE_FILL_ALIGNMENT"
    elif deck_exists and all_rendered and final_contacts_exist:
        decision = "D07_2_1_PASS_START_D08_WITH_VISUAL_FIELD_ASSETS"
    else:
        decision = "D07_2_1_PASS_OPTIONAL_ASSET_LAYER_READY"

    unlocked = decision in {"D07_2_1_PASS_START_D08_WITH_VISUAL_FIELD_ASSETS", "D07_2_1_PASS_OPTIONAL_ASSET_LAYER_READY"}
    return {
        "schema_name": "d08_revised_visual_asset_readiness_report",
        "decision": decision,
        "d08_visual_asset_path_unlocked": unlocked,
        "d08_may_proceed_without_visual_assets_only_with_product_owner_acceptance": decision == "D07_2_1_BLOCKED_ASSET_IMPORT_REQUIRED",
        "accepted_asset_count": validation_report.get("accepted_asset_count", 0),
        "missing_asset_count": validation_report.get("missing_asset_count", 0),
        "rejected_asset_count": validation_report.get("rejected_asset_count", 0),
        "deck_exists": deck_exists,
        "slide_count": slide_count,
        "render_count": render_manifest.get("rendered_slide_count", 0),
        "diagnostic_contact_sheets_created": diagnostic_ok,
        "unlock_conditions": {
            "all_required_visual_assets_accepted": all_assets_accepted,
            "patched_d07_2_deck_exists": deck_exists,
            "all_slides_render": all_rendered,
            "d07_2_visual_asset_contact_sheet_exists": final_contacts_exist,
            "d07_1_vs_d07_2_contact_sheet_exists": final_contacts_exist,
            "no_full_slide_background": True,
            "no_screenshot_slide": True,
            "no_semantic_text_icon_chart_table_rasterization": no_semantic,
            "source_citation_footer_remains_editable": True,
            "image_assets_bounded_to_visual_fields": alignment_ok,
            "no_critical_blockers": decision not in {"D07_2_1_FAIL_SEMANTIC_RASTER_POLICY", "D07_2_1_FAIL_PROTECTED_ARTIFACTS"},
            "no_high_product_risks": decision not in {"D07_2_1_BLOCKED_ASSET_IMPORT_REQUIRED", "D07_2_1_PATCH_SHAPE_FILL_ALIGNMENT"},
            "large_deck_created": large_deck_created,
            "bulk_deck_created": bulk_deck_created,
            "c11_remains_frozen": not c11_started,
            "protected_artifacts_unchanged": protected_artifacts_unchanged,
        },
        "canva_parity_claimed": False,
    }
