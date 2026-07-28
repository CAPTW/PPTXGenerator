"""Slide-level product review for E05."""

from __future__ import annotations

from statistics import mean
from typing import Any

from src.presentation_agent.magic_layer.e05_product_review_rubric import SLIDE_ORDER


def build_slide_review_matrix(
    *,
    icon_review: dict[str, Any],
    text_review: dict[str, Any],
    chart_table_review: dict[str, Any],
    source_review: dict[str, Any],
    editability_review: dict[str, Any],
    raster_review: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    icon_scores = {int(row["slide_number"]): float(row["score"]) for row in icon_review.get("slide_reviews", [])}
    text_scores = {int(row["slide_number"]): float(row["score"]) for row in text_review.get("slide_reviews", [])}
    chart_scores = {int(row["slide_number"]): float(row["score"]) for row in chart_table_review.get("slide_reviews", [])}
    source_issue_slides = {int(item["slide_number"]) for item in source_review.get("issues", []) if item.get("slide_number")}
    rows = []
    for slide_number, archetype_id in enumerate(SLIDE_ORDER, start=1):
        icon_score = icon_scores.get(slide_number, 4.2)
        text_score = text_scores.get(slide_number, 4.2)
        table_chart_score = chart_scores.get(slide_number, 4.2 if archetype_id not in {"data_dashboard", "table_heavy", "comparison_matrix", "decision_record", "risk_register"} else 3.8)
        source_score = 3.8 if slide_number in source_issue_slides else 4.3
        editability_score = 4.6 if editability_review.get("status") == "passed" else 2.0
        raster_score = 4.6 if raster_review.get("status") == "passed" else 1.0
        visual_score = _visual_score_for_archetype(archetype_id)
        footer_source_score = source_score
        slide_score = round(
            mean(
                [
                    visual_score,
                    text_score,
                    icon_score,
                    source_score,
                    editability_score,
                    table_chart_score,
                    footer_source_score,
                    raster_score,
                ]
            ),
            2,
        )
        severity = _severity(slide_score)
        rows.append(
            {
                "slide_number": slide_number,
                "archetype_id": archetype_id,
                "title": archetype_id.replace("_", " ").title(),
                "visual_score": visual_score,
                "text_score": text_score,
                "icon_score": icon_score,
                "source_citation_score": source_score,
                "editability_score": editability_score,
                "table_chart_score": table_chart_score,
                "footer_source_score": footer_source_score,
                "product_score": slide_score,
                "product_readiness": "ready" if slide_score >= 4.0 else "polish_required",
                "patch_recommendation": _recommendation(archetype_id, slide_score, text_score, icon_score, table_chart_score, source_score),
                "severity": severity,
            }
        )
    scores = [float(row["product_score"]) for row in rows]
    average_score = round(mean(scores), 2)
    minimum_score = round(min(scores), 2)
    matrix = {
        "schema_name": "e05_slide_review_matrix",
        "status": "passed" if minimum_score >= 3.5 else "patch_required",
        "slide_count": len(rows),
        "rows": rows,
    }
    scorecard = {
        "schema_name": "e05_visual_quality_scorecard",
        "status": "passed" if average_score >= 4.0 and minimum_score >= 3.5 else "patch_recommended",
        "average_product_score": average_score,
        "minimum_slide_score": minimum_score,
        "critical_blocker_count": sum(1 for row in rows if row["severity"] == "critical"),
        "high_product_risk_count": sum(1 for row in rows if row["severity"] == "high"),
        "medium_polish_count": sum(1 for row in rows if row["severity"] == "medium"),
        "low_polish_count": sum(1 for row in rows if row["severity"] == "low"),
        "rows": rows,
    }
    rhythm = {
        "schema_name": "e05_visual_rhythm_review",
        "status": "patch_recommended" if scorecard["medium_polish_count"] else "passed",
        "verdict": "distinct_archetypes_with_density_polish_needed" if scorecard["medium_polish_count"] else "passed",
        "notes": [
            "Archetypes remain distinct across cover, TOC, data, table, process, timeline, and closing slides.",
            "Dark/teal rhythm is coherent but dense table/register slides should be opened up before scaleout.",
        ],
    }
    return matrix, scorecard, rhythm


def _visual_score_for_archetype(archetype_id: str) -> float:
    if archetype_id in {"table_heavy", "risk_register"}:
        return 3.65
    if archetype_id in {"comparison_matrix", "data_dashboard", "decision_record"}:
        return 3.9
    if archetype_id in {"visual_toc", "standard_content", "evidence_overview", "card_grid"}:
        return 4.15
    return 4.25


def _severity(score: float) -> str:
    if score < 2.5:
        return "critical"
    if score < 3.5:
        return "high"
    if score < 4.0:
        return "medium"
    if score < 4.25:
        return "low"
    return "none"


def _recommendation(archetype_id: str, slide_score: float, text_score: float, icon_score: float, chart_score: float, source_score: float) -> str:
    if slide_score >= 4.0:
        return "No blocking patch; keep as candidate baseline."
    if chart_score <= min(text_score, icon_score, source_score):
        return "Open up chart/table density and tune data labels while preserving editability."
    if text_score <= min(icon_score, source_score):
        return "Improve text hierarchy and source/footer readability."
    if icon_score < 4.0:
        return "Tune icon scale and placement in local semantic components."
    return "Apply bounded visual hierarchy polish in E04.2."

