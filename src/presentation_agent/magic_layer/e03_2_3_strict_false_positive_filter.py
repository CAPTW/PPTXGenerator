"""Stricter false-positive filter for icon candidates."""

from __future__ import annotations

from typing import Any


CHROME_CONTEXTS = {
    "source_footer",
    "footer_action",
    "footer_filter",
    "primary_chart",
    "secondary_chart",
    "header_band",
    "timeline_axis",
}
TEXT_FRAGMENT_ROLES = {"source", "building", "citation"}
LINE_ROLE_CONTEXTS = {("chart_bar", "primary_chart"), ("pie_chart", "secondary_chart"), ("filter", "footer_filter"), ("table", "header_band"), ("timeline", "timeline_axis")}


def build_stricter_icon_hygiene_policy_v2() -> dict[str, Any]:
    return {
        "schema_name": "stricter_icon_hygiene_policy_v2",
        "status": "passed",
        "auto_reject_rules": [
            "dominant_pixels_are_text_fragments",
            "visible_component_is_card_edge_panel_border_or_source_strip",
            "foreground_touches_more_than_two_crop_edges_without_enclosed_glyph",
            "too_few_non_background_pixels",
            "mostly_straight_horizontal_or_vertical_line_segments",
            "role_confidence_depends_only_on_nearby_text",
            "partial_word_digit_or_label_fragment",
            "chart_axis_or_gridline_without_semantic_marker_role",
            "decorative_dot_line_cluster_without_icon_role",
        ],
        "human_review_triggers": [
            "p0_p1_crop_contains_glyph_and_large_container",
            "significant_text_contamination",
            "multiple_overlapping_glyphs",
            "partial_occlusion",
            "visually_complex_more_than_two_components",
            "no_library_match_and_local_trace_below_threshold",
            "vision_svg_differs_materially_from_crop",
        ],
    }


def apply_stricter_false_positive_filter(previous_hygiene_report: dict[str, Any]) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    decorative: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for row in previous_hygiene_report.get("candidates", []):
        classification, category, reason = _classify(row)
        updated = {
            **row,
            "strict_hygiene_classification": classification,
            "strict_hygiene_category": category,
            "strict_hygiene_reason": reason,
            "hygiene_metrics_v2": row.get("hygiene_metrics", {}),
            "clean_glyph_candidate_v2": classification in {"auto_accept_clean_icon_v2", "human_review_required_v2"},
        }
        rows.append(updated)
        if classification == "auto_accept_clean_icon_v2":
            accepted.append(updated)
        elif classification == "auto_reject_non_icon_v2":
            rejected.append(updated)
        elif classification == "decorative_optional_v2":
            decorative.append(updated)
        else:
            review.append(updated)
    return {
        "schema_name": "revised_false_positive_report",
        "status": "passed",
        "raw_candidate_count": len(rows),
        "previous_auto_accepted_count": previous_hygiene_report.get("auto_accept_clean_icon_count", 0),
        "previous_auto_rejected_count": previous_hygiene_report.get("auto_reject_non_icon_count", 0),
        "revised_auto_accepted_count": len(accepted),
        "revised_auto_rejected_count": len(rejected),
        "decorative_optional_count": len(decorative),
        "human_review_required_count": len(review),
        "auto_accept_clean_icons_v2": accepted,
        "auto_reject_non_icons_v2": rejected,
        "decorative_optional_icons_v2": decorative,
        "human_review_required_icons_v2": review,
        "accepted_or_review_icons": accepted + review,
        "candidates": rows,
    }


def _classify(row: dict[str, Any]) -> tuple[str, str, str]:
    metrics = row.get("hygiene_metrics", {})
    role = row.get("likely_role")
    context = row.get("component_context")
    prior = row.get("hygiene_classification")
    if prior == "auto_reject_non_icon":
        return "auto_reject_non_icon_v2", row.get("hygiene_category", "NOT_ICON"), "preserved_previous_reject"
    if prior == "decorative_optional":
        return "decorative_optional_v2", "DECORATIVE_ICON_OPTIONAL", "preserved_decorative_optional"
    if context in CHROME_CONTEXTS:
        if role in TEXT_FRAGMENT_ROLES:
            return "auto_reject_non_icon_v2", "TEXT_FRAGMENT_NOT_ICON", "text_or_source_strip_fragment"
        if (role, context) in LINE_ROLE_CONTEXTS:
            return "auto_reject_non_icon_v2", "CHART_TABLE_MARKER_NOT_ICON_UNLESS_SEMANTIC", "chart_or_table_axis_fragment"
        if context in {"footer_action", "footer_filter"}:
            return "decorative_optional_v2", "DECORATIVE_ICON_OPTIONAL", "footer_chrome_not_required_icon"
    if metrics.get("line_fragment_likeness", 0) > 0.75 and metrics.get("foreground_area_ratio", 0) < 0.07:
        return "auto_reject_non_icon_v2", "BORDER_FRAGMENT_NOT_ICON", "dominant_line_fragment"
    if metrics.get("text_likeness", 0) > 0.72 and metrics.get("component_count", 0) > 5:
        return "auto_reject_non_icon_v2", "TEXT_FRAGMENT_NOT_ICON", "text_like_component_cluster"
    if metrics.get("foreground_area_ratio", 0) < 0.008:
        return "auto_reject_non_icon_v2", "BACKGROUND_TEXTURE_NOT_ICON", "too_few_foreground_pixels"
    return "auto_accept_clean_icon_v2", "SEMANTIC_ICON_GLYPH_REQUIRED", "passed_strict_glyph_hygiene"
