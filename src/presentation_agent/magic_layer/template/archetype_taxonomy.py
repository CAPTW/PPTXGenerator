from __future__ import annotations

from copy import deepcopy
from typing import Any


ARCHETYPE_CONTRACTS: dict[str, dict[str, Any]] = {
    "cover_hero": {
        "archetype_id": "cover_hero",
        "intended_use": "cover or hero opening slide",
        "required_slots": ["SLOT_TITLE"],
        "optional_slots": ["SLOT_SUBTITLE", "SLOT_HERO_IMAGE", "SLOT_METADATA", "SLOT_FOOTER_SOURCE"],
        "forbidden_slots": ["full_slide_photo_with_baked_text", "full_slide_raster", "screenshot_slide"],
        "required_native_components": ["ppt_text_box"],
        "required_visual_fields": ["replaceable_image_frame_optional"],
        "required_footer_source_policy": "editable_if_present",
        "required_overflow_policy": "required_for_text_slots",
        "common_failure_modes": ["baked title text", "full-slide photo with text"],
        "review_focus": ["title bbox", "hero image crop", "residual raster text"],
        "patch_classes": ["PATCH_TEXT_REGION_LIFT", "PATCH_TEXT_OVERFLOW", "PATCH_RENDER_FIDELITY"],
    },
    "standard_content": {
        "archetype_id": "standard_content",
        "intended_use": "body content slide",
        "required_slots": ["SLOT_TITLE", "SLOT_BODY"],
        "optional_slots": ["SLOT_FOOTER_SOURCE", "SLOT_IMAGE"],
        "forbidden_slots": ["screenshot_slide", "raster_body_text"],
        "required_native_components": ["ppt_text_box", "ppt_shape_group"],
        "required_visual_fields": [],
        "required_footer_source_policy": "editable_if_present",
        "required_overflow_policy": "required_for_text_slots",
        "common_failure_modes": ["text overflow", "rasterized body"],
        "review_focus": ["body text overflow"],
        "patch_classes": ["PATCH_TEXT_OVERFLOW", "PATCH_OBJECT_BBOX"],
    },
    "data_dashboard": {
        "archetype_id": "data_dashboard",
        "intended_use": "metric and chart dashboard",
        "required_slots": ["SLOT_KPI_VALUE_01", "SLOT_KPI_LABEL_01", "SLOT_CHART_MAIN"],
        "optional_slots": ["SLOT_TITLE", "SLOT_FOOTER_SOURCE"],
        "forbidden_slots": ["dashboard_screenshot", "raster_chart_fallback"],
        "required_native_components": ["native_chart_or_editable_shape_chart"],
        "required_visual_fields": [],
        "required_footer_source_policy": "editable_if_present",
        "required_overflow_policy": "required_for_text_slots",
        "common_failure_modes": ["chart raster fallback", "KPI label raster"],
        "review_focus": ["chart native/editable status", "KPI text editability"],
        "patch_classes": ["PATCH_CHART_NATIVE_RECONSTRUCTION", "PATCH_TEXT_REGION_LIFT"],
    },
    "table_heavy": {
        "archetype_id": "table_heavy",
        "intended_use": "table-dominant slide",
        "required_slots": ["SLOT_TABLE_MAIN", "SLOT_TABLE_HEADER_01", "SLOT_TABLE_BODY_01"],
        "optional_slots": ["SLOT_TITLE", "SLOT_FOOTER_SOURCE"],
        "forbidden_slots": ["spreadsheet_screenshot", "raster_table_fallback"],
        "required_native_components": ["native_table_or_editable_shape_grid_table"],
        "required_visual_fields": [],
        "required_footer_source_policy": "editable_if_present",
        "required_overflow_policy": "required_for_table_text",
        "common_failure_modes": ["raster table", "table text overflow"],
        "review_focus": ["native table status", "cell text overflow"],
        "patch_classes": ["PATCH_TABLE_NATIVE_RECONSTRUCTION", "PATCH_TEXT_OVERFLOW"],
    },
    "executive_summary": {"archetype_id": "executive_summary", "intended_use": "summary", "required_slots": ["SLOT_TITLE", "SLOT_SUMMARY"], "optional_slots": ["SLOT_KPI_VALUE_01"], "forbidden_slots": ["screenshot_slide"], "required_native_components": ["ppt_text_box"], "required_visual_fields": [], "required_footer_source_policy": "editable_if_present", "required_overflow_policy": "required_for_text_slots", "common_failure_modes": ["dense text"], "review_focus": ["overflow"], "patch_classes": ["PATCH_TEXT_OVERFLOW"]},
    "section_divider": {"archetype_id": "section_divider", "intended_use": "section break", "required_slots": ["SLOT_TITLE"], "optional_slots": ["SLOT_SUBTITLE"], "forbidden_slots": ["full_slide_raster"], "required_native_components": ["ppt_text_box"], "required_visual_fields": [], "required_footer_source_policy": "optional", "required_overflow_policy": "required_for_text_slots", "common_failure_modes": ["baked title"], "review_focus": ["title"], "patch_classes": ["PATCH_TEXT_REGION_LIFT"]},
    "two_column_comparison": {"archetype_id": "two_column_comparison", "intended_use": "comparison", "required_slots": ["SLOT_LEFT_TITLE", "SLOT_RIGHT_TITLE"], "optional_slots": ["SLOT_LEFT_BODY", "SLOT_RIGHT_BODY"], "forbidden_slots": ["raster_text"], "required_native_components": ["ppt_text_box", "ppt_shape_group"], "required_visual_fields": [], "required_footer_source_policy": "editable_if_present", "required_overflow_policy": "required_for_text_slots", "common_failure_modes": ["column overflow"], "review_focus": ["column geometry"], "patch_classes": ["PATCH_OBJECT_BBOX"]},
    "three_card_insight": {"archetype_id": "three_card_insight", "intended_use": "card insights", "required_slots": ["SLOT_CARD_01_TITLE", "SLOT_CARD_02_TITLE", "SLOT_CARD_03_TITLE"], "optional_slots": ["SLOT_CARD_01_BODY"], "forbidden_slots": ["raster_card_text"], "required_native_components": ["card_panel", "ppt_text_box"], "required_visual_fields": [], "required_footer_source_policy": "editable_if_present", "required_overflow_policy": "required_for_text_slots", "common_failure_modes": ["card text raster"], "review_focus": ["card panels"], "patch_classes": ["PATCH_TEXT_REGION_LIFT"]},
    "process_timeline": {"archetype_id": "process_timeline", "intended_use": "process timeline", "required_slots": ["SLOT_TIMELINE_STEP_01", "SLOT_TIMELINE_LABEL_01"], "optional_slots": ["SLOT_TITLE"], "forbidden_slots": ["raster_timeline_screenshot"], "required_native_components": ["editable_timeline"], "required_visual_fields": [], "required_footer_source_policy": "editable_if_present", "required_overflow_policy": "required_for_text_slots", "common_failure_modes": ["timeline raster screenshot"], "review_focus": ["connector shapes"], "patch_classes": ["PATCH_TIMELINE_NATIVE_RECONSTRUCTION"]},
    "framework_2x2_matrix": {"archetype_id": "framework_2x2_matrix", "intended_use": "2x2 framework", "required_slots": ["SLOT_MATRIX_QUADRANT_01"], "optional_slots": ["SLOT_TITLE"], "forbidden_slots": ["raster_matrix"], "required_native_components": ["editable_matrix"], "required_visual_fields": [], "required_footer_source_policy": "editable_if_present", "required_overflow_policy": "required_for_text_slots", "common_failure_modes": ["matrix screenshot"], "review_focus": ["quadrants"], "patch_classes": ["PATCH_MATRIX_NATIVE_RECONSTRUCTION"]},
    "chart_focus": {"archetype_id": "chart_focus", "intended_use": "chart focus", "required_slots": ["SLOT_CHART_MAIN"], "optional_slots": ["SLOT_TITLE", "SLOT_FOOTER_SOURCE"], "forbidden_slots": ["raster_chart_fallback"], "required_native_components": ["native_chart_or_editable_shape_chart"], "required_visual_fields": [], "required_footer_source_policy": "editable_if_present", "required_overflow_policy": "required_for_text_slots", "common_failure_modes": ["chart labels raster"], "review_focus": ["chart native status"], "patch_classes": ["PATCH_CHART_NATIVE_RECONSTRUCTION"]},
    "appendix_reference": {"archetype_id": "appendix_reference", "intended_use": "appendix/reference", "required_slots": ["SLOT_REFERENCE_TEXT"], "optional_slots": ["SLOT_CITATION_LIST"], "forbidden_slots": ["scanned_reference_image"], "required_native_components": ["ppt_text_box"], "required_visual_fields": [], "required_footer_source_policy": "editable_required", "required_overflow_policy": "required_for_text_slots", "common_failure_modes": ["scanned appendix"], "review_focus": ["text editability"], "patch_classes": ["PATCH_TEXT_REGION_LIFT"]},
    "image_story": {"archetype_id": "image_story", "intended_use": "image-led story", "required_slots": ["SLOT_IMAGE_MAIN"], "optional_slots": ["SLOT_CAPTION", "SLOT_CALLOUT"], "forbidden_slots": ["caption_baked_into_image"], "required_native_components": ["replaceable_image_frame", "ppt_text_box"], "required_visual_fields": ["replaceable_image_frame"], "required_footer_source_policy": "editable_if_present", "required_overflow_policy": "required_for_text_slots", "common_failure_modes": ["caption raster"], "review_focus": ["caption/callout"], "patch_classes": ["PATCH_RASTER_TEXT_SUPPRESSION"]},
    "quote_pullout": {"archetype_id": "quote_pullout", "intended_use": "quote", "required_slots": ["SLOT_QUOTE", "SLOT_ATTRIBUTION"], "optional_slots": [], "forbidden_slots": ["quote_image"], "required_native_components": ["ppt_text_box"], "required_visual_fields": [], "required_footer_source_policy": "optional", "required_overflow_policy": "required_for_text_slots", "common_failure_modes": ["quote raster"], "review_focus": ["quote text"], "patch_classes": ["PATCH_TEXT_OVERFLOW"]},
    "case_study": {"archetype_id": "case_study", "intended_use": "case study", "required_slots": ["SLOT_CASE_TITLE", "SLOT_CASE_BODY"], "optional_slots": ["SLOT_METRIC_01"], "forbidden_slots": ["case_panel_screenshot"], "required_native_components": ["card_panel", "ppt_text_box"], "required_visual_fields": [], "required_footer_source_policy": "editable_if_present", "required_overflow_policy": "required_for_text_slots", "common_failure_modes": ["panel raster"], "review_focus": ["panel editability"], "patch_classes": ["PATCH_TEXT_REGION_LIFT"]},
    "roadmap_milestones": {"archetype_id": "roadmap_milestones", "intended_use": "roadmap", "required_slots": ["SLOT_ROADMAP_MILESTONE_01"], "optional_slots": ["SLOT_TITLE"], "forbidden_slots": ["raster_roadmap"], "required_native_components": ["editable_roadmap"], "required_visual_fields": [], "required_footer_source_policy": "editable_if_present", "required_overflow_policy": "required_for_text_slots", "common_failure_modes": ["roadmap screenshot"], "review_focus": ["milestone geometry"], "patch_classes": ["PATCH_ROADMAP_NATIVE_RECONSTRUCTION"]},
}


def get_archetype_contract(archetype_id: str) -> dict[str, Any]:
    return deepcopy(ARCHETYPE_CONTRACTS[archetype_id])


def known_archetype(archetype_id: str | None) -> bool:
    return bool(archetype_id and archetype_id in ARCHETYPE_CONTRACTS)


def validate_archetype_contract(archetype_id: str, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    if not known_archetype(archetype_id):
        return {"pass": False, "failures": [f"{archetype_id} is not a known archetype"]}
    taxonomy = ARCHETYPE_CONTRACTS[archetype_id]
    failures = []
    if contract:
        slots = set(contract.get("editable_content_slots", []) + contract.get("native_component_slots", []) + contract.get("replaceable_visual_slots", []))
        for slot in taxonomy.get("required_slots", []):
            if slot not in slots and not slot.endswith("*") and "KPI" not in slot:
                failures.append(f"required taxonomy slot missing: {slot}")
    return {"pass": not failures, "failures": failures, "taxonomy": deepcopy(taxonomy)}
