"""Controlled product baseline rubric for E06."""

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


def build_e06_product_baseline_rubric_v1() -> dict[str, Any]:
    return {
        "schema_name": "e06_product_baseline_rubric_v1",
        "status": "active",
        "score_scale": {
            "5.0": "production baseline quality",
            "4.5": "strong baseline candidate",
            "4.0": "acceptable baseline, minor polish only",
            "3.5": "usable but not baseline-ready",
            "below_3.5": "patch required",
        },
        "categories": [
            "reference_to_editable_conversion_fidelity",
            "source_bound_content_clarity",
            "source_citation_traceability",
            "semantic_editability",
            "icon_system_quality",
            "dense_slide_readability",
            "chart_table_readability",
            "typography_and_hierarchy",
            "visual_rhythm_and_archetype_distinction",
            "source_footer_consistency",
            "no_raster_policy",
            "editable_deck_product_usability",
        ],
        "hard_blockers": [
            "source_citation_binding_regression",
            "slot_binding_regression",
            "semantic_raster_content",
            "full_slide_raster",
            "screenshot_slide",
            "hidden_fake_editability",
            "text_below_6pt",
            "text_overflow_or_clipping",
            "invisible_or_unanchored_semantic_icon",
            "unreadable_dense_table_or_chart",
            "contract_v2_failure",
            "protected_artifact_change",
        ],
        "thresholds": {
            "average_product_baseline_score_min": 4.35,
            "minimum_slide_score_min": 4.0,
            "critical_blocker_count": 0,
            "high_product_risk_count": 0,
            "maximum_medium_polish_count": 3,
        },
        "slide_order": SLIDE_ORDER,
        "broad_canva_parity_claimed": False,
    }

