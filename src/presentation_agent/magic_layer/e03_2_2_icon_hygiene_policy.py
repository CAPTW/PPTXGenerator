"""Icon candidate hygiene policy for E03.2.2."""

from __future__ import annotations

from typing import Any


def build_icon_candidate_hygiene_policy_v1() -> dict[str, Any]:
    return {
        "schema_name": "icon_candidate_hygiene_policy_v1",
        "status": "passed",
        "candidate_categories": [
            "SEMANTIC_ICON_GLYPH_REQUIRED",
            "SEMANTIC_ICON_CONTAINER_ONLY",
            "ICON_CONTAINER_PLUS_GLYPH",
            "DECORATIVE_ICON_OPTIONAL",
            "DECORATIVE_MARK_NOT_ICON",
            "TEXT_FRAGMENT_NOT_ICON",
            "BORDER_FRAGMENT_NOT_ICON",
            "PANEL_CORNER_NOT_ICON",
            "BACKGROUND_TEXTURE_NOT_ICON",
            "CHART_TABLE_MARKER_NOT_ICON_UNLESS_SEMANTIC",
            "LOW_CONFIDENCE_REVIEW_REQUIRED",
        ],
        "hard_reject_rules": [
            "crop_is_mostly_text",
            "crop_is_mostly_panel_border",
            "crop_is_mostly_card_corner",
            "crop_is_mostly_source_footer_line",
            "crop_is_background_texture_only",
            "crop_contains_no_meaningful_glyph_strokes",
            "crop_is_only_partial_letter_or_number",
            "crop_is_blank_patch",
            "crop_is_only_decorative_line_without_semantic_marker_role",
        ],
        "human_review_scope": [
            "ambiguous_p0_or_p1_semantic_icon",
            "uncertain_glyph_container_split",
            "no_match_clean_glyph_requiring_trace",
            "risky_auto_reject_sample",
        ],
        "forbidden_pass_paths": [
            "contaminated_crop_svg_trace",
            "role_only_substitution",
            "generic_icon_fallback",
            "semantic_raster_icon",
        ],
    }
