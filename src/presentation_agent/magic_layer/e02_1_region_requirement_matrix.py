"""Region requirements and reference-fidelity policy for E02.1."""

from __future__ import annotations

from typing import Any


REGION_REQUIREMENTS: dict[str, list[str]] = {
    "cover_hero": [
        "title_cluster",
        "subtitle_value_promise",
        "meta_bar",
        "diagonal_visual_divider_chrome",
        "hero_visual_field",
        "footer_source_strip",
        "technical_line_accents",
        "editorial_asymmetry",
    ],
    "standard_content": [
        "large_title_panel_chrome",
        "four_content_modules",
        "angled_white_card_geometry",
        "icon_zones",
        "right_insight_rail",
        "left_technical_circuit_chrome",
        "footer_source_strip",
        "premium_shadow_border_details",
    ],
    "data_dashboard": [
        "title_header_chrome",
        "kpi_row_cards_with_icons",
        "primary_chart_frame",
        "secondary_insight_chart_panel",
        "annotation_source_footer_strip",
        "editable_chart_table_semantics",
        "dashboard_visual_density",
    ],
    "table_heavy": [
        "title_header_chrome",
        "dense_table_grid",
        "header_band_with_icon_zones",
        "side_rail_icon_group",
        "kpi_note_footer_strips",
        "row_column_grouping",
        "editable_shape_grid_table",
        "premium_borders_chrome",
    ],
}


def build_reference_fidelity_policy() -> dict[str, Any]:
    return {
        "schema_name": "e02_1_reference_fidelity_policy_v1",
        "status": "active",
        "pass_requires": [
            "not_just_editable_skeleton",
            "major_reference_regions_preserved",
            "reference_specific_chrome_reconstructed_as_native_vector_or_ppt",
            "semantic_components_editable",
            "bounded_visual_fields_intentionally_preserved",
            "charts_tables_native_or_editable_shape_and_visually_close_enough",
            "table_grid_chrome_density_preserved",
            "no_generic_white_block_template_regression",
            "no_hidden_screenshot_or_full_slide_raster",
            "no_semantic_raster_fallback",
            "region_level_fidelity_pass",
        ],
        "whole_slide_similarity_alone_is_sufficient": False,
        "broad_canva_parity_claimed": False,
    }


def build_visual_asset_policy() -> dict[str, Any]:
    return {
        "schema_name": "e02_1_visual_asset_policy",
        "status": "active",
        "allowed": [
            "bounded_hero_photo_or_abstract_visual_field",
            "bounded_nonsemantic_decorative_chrome_crop",
            "replaceable_visual_field_frame",
        ],
        "forbidden": [
            "full_slide_reference_background",
            "screenshot_slide",
            "semantic_text_as_raster",
            "semantic_icon_as_raster",
            "semantic_chart_table_as_raster",
            "semantic_card_panel_as_raster",
            "footer_source_as_raster",
        ],
        "requires_bbox_slot_ledger": True,
        "requires_replaceable_or_decorative_classification": True,
        "api_key_image_generation_allowed": False,
    }


def build_region_requirement_matrix() -> dict[str, Any]:
    return {
        "schema_name": "e02_1_region_requirement_matrix",
        "status": "active",
        "archetypes": {
            archetype_id: [{"region_id": region, "required": True, "semantic_raster_allowed": False} for region in regions]
            for archetype_id, regions in REGION_REQUIREMENTS.items()
        },
    }


def required_regions(archetype_id: str) -> list[str]:
    return REGION_REQUIREMENTS[archetype_id]
