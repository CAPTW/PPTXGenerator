"""Contract tuning parameter schema for E06.3."""

from __future__ import annotations

from typing import Any


ALLOWED_PARAMETERS = [
    "icon_size_token_delta",
    "icon_anchor_offset",
    "card_padding_delta",
    "table_row_height_delta",
    "table_column_width_delta",
    "chart_region_scale",
    "source_footer_font_size_delta",
    "source_footer_y_offset",
    "title_region_spacing",
    "side_rail_width_delta",
    "data_label_visibility_mode",
    "visual_asset_crop_mode",
    "panel_fill_opacity_delta",
    "line_weight_delta",
    "contrast_token_delta",
    "z_order_adjustment",
]

FORBIDDEN_PARAMETERS = [
    "source_text_deletion",
    "citation_deletion",
    "semantic_rasterization",
    "unbound_claim_creation",
    "arbitrary_magic_coordinates",
    "slide_xml_wholesale_copy",
]


def build_contract_tuning_parameter_schema_v1() -> dict[str, Any]:
    return {
        "schema_name": "contract_tuning_parameter_schema_v1",
        "status": "passed",
        "allowed_parameters": [
            {
                "parameter_id": parameter,
                "value_type": _value_type(parameter),
                "requires_contract_diff_record": True,
                "requires_preservation_gate": True,
            }
            for parameter in ALLOWED_PARAMETERS
        ],
        "forbidden_parameters": FORBIDDEN_PARAMETERS,
        "source_content_change_allowed": False,
        "semantic_raster_fallback_allowed": False,
        "arbitrary_coordinate_edits_allowed": False,
    }


def _value_type(parameter: str) -> str:
    if parameter.endswith("_mode"):
        return "enum"
    if parameter == "z_order_adjustment":
        return "integer_delta"
    return "inch_or_token_delta"
