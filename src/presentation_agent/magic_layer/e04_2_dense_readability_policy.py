"""Dense readability policy for E04.2 product polish."""

from __future__ import annotations

from typing import Any


TARGET_SLIDES = {
    9: "comparison_matrix",
    11: "table_heavy",
    14: "risk_register",
}


def build_e04_2_dense_readability_policy() -> dict[str, Any]:
    return {
        "schema_name": "e04_2_dense_readability_policy",
        "status": "active",
        "hard_requirements": {
            "visible_text_min_pt": 6.0,
            "preferred_body_table_source_min_pt": 7.0,
            "preferred_table_header_min_pt": 7.5,
            "text_overflow_count": 0,
            "text_clipping_count": 0,
            "semantic_text_raster_allowed": False,
        },
        "allowed_dense_data_strategies": [
            "increase_table_region_width_height",
            "reduce_nonessential_visual_chrome_on_dense_slides",
            "use_source_bound_short_labels_with_full_detail_retained_in_ledgers",
            "group_rows_into_readable_bands",
            "improve_row_column_spacing",
            "increase_footer_source_contrast_and_font_size",
        ],
        "forbidden": [
            "delete_required_source_bound_content_without_ledger",
            "fabricate_summaries",
            "rasterize_text_or_tables",
            "break_source_citation_bindings",
            "collapse_dense_table_into_placeholder",
            "add_new_slides_without_approval",
        ],
        "target_slides": TARGET_SLIDES,
    }

