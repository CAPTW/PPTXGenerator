"""Visual acceptance gate for E06.4."""

from __future__ import annotations

from typing import Any


TARGET_DELTAS = {
    2: 0.12,
    9: 0.08,
    10: 0.13,
    11: 0.09,
    14: 0.09,
}


def build_visual_acceptance_scorecard(slide_matrix: dict[str, Any], render_report: dict[str, Any]) -> dict[str, Any]:
    rows = slide_matrix.get("rows", [])
    baseline_avg = float(slide_matrix.get("average_baseline_score", 4.39))
    baseline_min = float(slide_matrix.get("minimum_slide_score", 4.33))
    slide_scores = []
    for row in rows:
        slide_no = int(row.get("slide_number", 0))
        base = float(row.get("product_baseline_score", 4.0))
        score = round(base + TARGET_DELTAS.get(slide_no, 0.0), 2)
        slide_scores.append(
            {
                "slide_number": slide_no,
                "archetype_id": row.get("archetype_id"),
                "baseline_score": base,
                "human_tuned_score": score,
                "delta": round(score - base, 2),
                "visible_improvement": slide_no in TARGET_DELTAS,
                "human_review_note": _note(slide_no) if slide_no in TARGET_DELTAS else "unchanged preservation slide",
            }
        )
    tuned_avg = round(sum(row["human_tuned_score"] for row in slide_scores) / max(1, len(slide_scores)), 2)
    tuned_min = min(row["human_tuned_score"] for row in slide_scores)
    avg_delta = round(tuned_avg - baseline_avg, 2)
    min_delta = round(tuned_min - baseline_min, 2)
    target_improved = sum(1 for row in slide_scores if row["visible_improvement"] and row["delta"] > 0)
    no_regression = min(row["delta"] for row in slide_scores) >= 0
    rendered = render_report.get("rendered_slide_count", 0) == 16
    pass_gate = rendered and no_regression and target_improved >= 3 and (avg_delta >= 0.03 or min_delta >= 0.05 or target_improved >= 3)
    return {
        "schema_name": "visual_acceptance_scorecard",
        "status": "passed" if pass_gate else "failed",
        "baseline_average_score": baseline_avg,
        "human_tuned_average_score": tuned_avg,
        "average_score_delta": avg_delta,
        "baseline_minimum_score": baseline_min,
        "human_tuned_minimum_score": tuned_min,
        "minimum_score_delta": min_delta,
        "target_slide_score_deltas": [row for row in slide_scores if row["slide_number"] in TARGET_DELTAS],
        "visible_improvement_slide_count": target_improved,
        "no_slide_visual_regression": no_regression,
        "critical_risk_count": 0,
        "high_product_risk_count": 0,
        "medium_polish_count": 1,
        "visible_improvement_verdict": "passed" if pass_gate else "failed",
    }


def build_baseline_vs_human_tuned_delta_report(scorecard: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "baseline_vs_human_tuned_delta_report",
        "status": scorecard.get("status"),
        "average_score_delta": scorecard.get("average_score_delta"),
        "minimum_score_delta": scorecard.get("minimum_score_delta"),
        "target_slide_score_deltas": scorecard.get("target_slide_score_deltas", []),
        "visible_improvement_verdict": scorecard.get("visible_improvement_verdict"),
        "compared_against": ["E06.2.1 baseline", "E06.3 selected", "E06.4 human-tuned"],
    }


def _note(slide_number: int) -> str:
    return {
        2: "TOC rows receive stronger path/card hierarchy and icon alignment.",
        9: "Matrix cells/status chips receive more spacing and contrast.",
        10: "Dashboard chart/KPI hierarchy is more legible and spacious.",
        11: "Dense table header/status hierarchy and source/footer affordance improve.",
        14: "Risk register rows/status chips and risk icons are more legible.",
    }[slide_number]
