"""Product review rubric for E05 source-bound deck QA."""

from __future__ import annotations

from typing import Any


SLIDE_ORDER = [
    "cover_hero",
    "visual_toc",
    "section_divider",
    "standard_content",
    "evidence_overview",
    "card_grid",
    "methodology_framework",
    "process_flow",
    "comparison_matrix",
    "data_dashboard",
    "table_heavy",
    "timeline_roadmap",
    "decision_record",
    "risk_register",
    "case_study",
    "closing_synthesis",
]


def build_e05_product_review_rubric_v1() -> dict[str, Any]:
    categories = [
        "source_bound_content_clarity",
        "layout_fidelity",
        "semantic_editability",
        "icon_placement_quality",
        "icon_size_contrast",
        "text_readability",
        "table_chart_readability",
        "card_panel_visual_hierarchy",
        "footer_source_citation_readability",
        "visual_rhythm",
        "editable_template_usefulness",
        "no_raster_compliance",
        "debug_artifact_absence",
    ]
    return {
        "schema_name": "e05_product_review_rubric_v1",
        "status": "active",
        "score_scale": {
            "5": "production-ready",
            "4": "minor polish only",
            "3": "acceptable but patch recommended",
            "2": "product risk, patch required",
            "1": "blocker",
        },
        "categories": categories,
        "hard_blockers": [
            "missing_source_binding",
            "missing_citation_binding",
            "text_overflow_or_clipping",
            "semantic_raster_icon_chart_table_text",
            "invisible_semantic_icon",
            "unanchored_semantic_icon",
            "generic_placeholder_icon",
            "unreadable_table_or_chart",
            "full_slide_raster",
            "screenshot_slide",
            "unknown_content_bearing_layer",
            "protected_artifact_change",
        ],
        "e06_thresholds": {
            "average_product_score_min": 4.0,
            "minimum_slide_score_min": 3.5,
            "critical_blocker_count": 0,
            "high_product_risk_count": 0,
        },
        "slide_order": SLIDE_ORDER,
        "broad_canva_parity_claimed": False,
    }

