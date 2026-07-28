"""Shared design system tokens for the E03 editable template pack."""

from __future__ import annotations

from typing import Any


REQUIRED_TOKEN_KEYS = {
    "palette",
    "typography_scale",
    "spacing_scale",
    "card_style",
    "footer_style",
    "chart_style",
    "table_style",
    "connector_style",
    "icon_style",
    "photo_image_frame_style",
    "decorative_motif_rules",
    "raster_policy",
    "protected_text_zone_policy",
}


def build_design_system_tokens() -> dict[str, Any]:
    return {
        "schema_name": "e03_design_system_tokens",
        "palette": {"deep_navy": "#061526", "dark_teal": "#0C313D", "off_white": "#F8FAFC", "muted_gold": "#F4B43F", "cyan": "#2DD4FF"},
        "typography_scale": {"title": 30, "subtitle": 14, "body": 10, "footer": 7, "kpi": 16},
        "spacing_scale": {"xs": 0.01, "sm": 0.02, "md": 0.04, "lg": 0.07},
        "card_style": {"fill": "dark_teal", "stroke": "cyan", "radius": 0.018},
        "footer_style": {"fill": "#04101D", "rule": "muted_gold", "text": "off_white"},
        "chart_style": {"series": "cyan", "axis_rule": "muted_gold", "target": "native_chart"},
        "table_style": {"header_fill": "#124353", "body_fill": "dark_teal", "target": "native_table_or_shape_grid"},
        "connector_style": {"stroke": "cyan", "width_pt": 1.1, "target": "ppt_connector"},
        "icon_style": {"style": "cyan_circle_with_inner_triangle", "target": "native_vector"},
        "photo_image_frame_style": {"shape": "rounded_rect", "replaceable": True, "bounded": True},
        "decorative_motif_rules": {"margins_only": True, "may_cover_text": False},
        "raster_policy": {"full_slide_raster": "forbidden", "semantic_raster": "forbidden", "bounded_nonsemantic_visuals": "allowed_with_documentation"},
        "protected_text_zone_policy": {"overlap_allowed": False, "editable_required": True},
        "canva_parity_claimed": False,
    }


def validate_design_system_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(REQUIRED_TOKEN_KEYS - set(tokens))
    failures = []
    if tokens.get("raster_policy", {}).get("full_slide_raster") != "forbidden":
        failures.append("full_slide_raster_policy_not_forbidden")
    if tokens.get("raster_policy", {}).get("semantic_raster") != "forbidden":
        failures.append("semantic_raster_policy_not_forbidden")
    return {"schema_name": "e03_design_system_tokens_validation", "status": "passed" if not missing and not failures else "failed", "missing": missing, "failures": failures, "canva_parity_claimed": False}
