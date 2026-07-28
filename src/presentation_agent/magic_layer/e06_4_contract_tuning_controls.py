"""Contract tuning controls v2 for E06.4."""

from __future__ import annotations

from typing import Any


ALLOWED_CONTROLS = [
    "title_region_spacing",
    "card_padding_delta",
    "table_row_height_delta",
    "table_column_width_delta",
    "chart_region_scale",
    "chart_panel_padding",
    "source_footer_font_size_delta",
    "source_footer_contrast_token",
    "icon_anchor_offset",
    "icon_size_token_delta",
    "side_rail_width_delta",
    "panel_fill_opacity_delta",
    "panel_contrast_token",
    "line_weight_delta",
    "data_label_visibility_mode",
    "active_state_emphasis_token",
]


def build_contract_tuning_controls_v2() -> dict[str, Any]:
    return {
        "schema_name": "contract_tuning_controls_v2",
        "status": "passed",
        "allowed_controls": [
            {
                "control_id": control,
                "human_guided": True,
                "requires_change_reason": True,
                "requires_preservation_gate": True,
            }
            for control in ALLOWED_CONTROLS
        ],
        "forbidden_controls": [
            "source_bound_content_deletion",
            "citation_deletion",
            "semantic_rasterization",
            "arbitrary_object_edits_outside_contract",
            "text_contrast_weakening",
            "hidden_detail_for_fake_cleanliness",
            "global_all_slide_changes_without_reason",
        ],
    }
