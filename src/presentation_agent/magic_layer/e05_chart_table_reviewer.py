"""Chart and table readability review for E05."""

from __future__ import annotations

from typing import Any


CHART_TABLE_SLIDES = {
    9: ("comparison_matrix", "editable_shape_grid_table"),
    10: ("data_dashboard", "editable_shape_chart"),
    11: ("table_heavy", "editable_shape_grid_table"),
    13: ("decision_record", "editable_shape_grid_table"),
    14: ("risk_register", "editable_shape_grid_table"),
}


def review_chart_table_readability(e04_report: dict[str, Any], text_review: dict[str, Any]) -> dict[str, Any]:
    text_by_slide = {int(row["slide_number"]): row for row in text_review.get("slide_reviews", [])}
    slide_reviews = []
    issues = []
    for slide_number, (archetype_id, component_type) in CHART_TABLE_SLIDES.items():
        text_row = text_by_slide.get(slide_number, {})
        score = 4.25
        notes = []
        if text_row.get("tiny_text_run_count", 0):
            score -= 0.35
            notes.append("table/chart labels include sub-6pt text")
        if text_row.get("text_box_count", 0) > 30:
            score -= 0.45
            notes.append("dense grid/table content should be opened up")
        if archetype_id in {"table_heavy", "risk_register"}:
            score -= 0.3
            notes.append("register/table slide is readable enough for validation but not polished")
        if archetype_id == "comparison_matrix":
            score -= 0.15
            notes.append("matrix labels are compact and need product-polish review")
        score = round(max(1.0, score), 2)
        if score < 4.0:
            issues.append(
                {
                    "slide_number": slide_number,
                    "archetype_id": archetype_id,
                    "issue": "; ".join(notes),
                    "severity": "medium" if score >= 3.5 else "high",
                    "patch_type": "table_density_patch" if "table" in component_type else "chart_readability_patch",
                    "recommended_action": "Reduce density and tune labels while preserving source-bound values and editable shape components.",
                }
            )
        slide_reviews.append(
            {
                "slide_number": slide_number,
                "archetype_id": archetype_id,
                "component_type": component_type,
                "score": score,
                "status": "passed" if score >= 3.5 else "patch_required",
                "notes": notes,
            }
        )
    return {
        "schema_name": "e05_table_chart_readability_review",
        "status": "patch_recommended" if issues else "passed",
        "native_ppt_chart_count": e04_report.get("native_ppt_chart_count", 0),
        "editable_shape_chart_count": e04_report.get("editable_shape_chart_count", 0),
        "raster_chart_count": e04_report.get("raster_chart_count", 0),
        "native_ppt_table_count": e04_report.get("native_ppt_table_count", 0),
        "editable_shape_grid_table_count": e04_report.get("editable_shape_grid_table_count", 0),
        "raster_table_count": e04_report.get("raster_table_count", 0),
        "slide_reviews": slide_reviews,
        "issues": issues,
    }

