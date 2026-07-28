"""Human visual acceptance rubric for E06.4."""

from __future__ import annotations

from typing import Any


def build_human_visual_acceptance_rubric_v1() -> dict[str, Any]:
    return {
        "schema_name": "human_visual_acceptance_rubric_v1",
        "status": "passed",
        "promotion_grade_improvement_requires": [
            "average_product_score_delta >= +0.03",
            "or minimum_slide_score_delta >= +0.05",
            "or at least 3 targeted slides visibly improve by human-review rubric",
            "no slide visually regresses",
            "target slide changes visible at contact-sheet scale",
            "dense slide readability does not regress",
            "source/citation/slot binding does not regress",
            "semantic editability and icon system do not regress",
        ],
        "hard_rejection_conditions": [
            "visually_identical_candidate",
            "score_only_improvement_without_visible_change",
            "weaker_contrast_or_hierarchy",
            "source_footer_readability_regression",
            "dense_table_regression",
            "icon_placement_regression",
            "protected_artifact_change",
        ],
        "target_slide_count_required_for_visual_acceptance": 3,
        "minimum_average_score_delta": 0.03,
        "minimum_slide_score_delta_floor": 0.0,
        "broad_canva_parity_claimed": False,
    }
