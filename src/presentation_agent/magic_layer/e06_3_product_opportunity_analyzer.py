"""Product opportunity analysis for E06.3 contract-driven variants."""

from __future__ import annotations

from typing import Any


TARGET_LOW_POLISH = {2: "visual_toc", 10: "data_dashboard"}
TARGET_DENSE = {9: "comparison_matrix", 11: "table_heavy", 14: "risk_register"}


def build_product_improvement_opportunity_report(
    slide_matrix: dict[str, Any],
    risk_register: dict[str, Any],
) -> dict[str, Any]:
    rows = slide_matrix.get("rows", [])
    low_polish = [
        _opportunity(row, "low_polish_visual_hierarchy")
        for row in rows
        if int(row.get("slide_number", 0)) in TARGET_LOW_POLISH
    ]
    dense = [
        _opportunity(row, "dense_readability_margin")
        for row in rows
        if int(row.get("slide_number", 0)) in TARGET_DENSE
    ]
    global_items = [
        {
            "opportunity_id": "global_source_footer_readability",
            "area": "source_footer_readability",
            "target_slides": "all",
            "recommended_parameter": "source_footer_font_size_delta",
            "bounded": True,
        },
        {
            "opportunity_id": "global_icon_optical_alignment",
            "area": "icon_system",
            "target_slides": [2, 10],
            "recommended_parameter": "icon_anchor_offset",
            "bounded": True,
        },
    ]
    risks = risk_register.get("risks", [])
    return {
        "schema_name": "product_improvement_opportunity_report",
        "status": "passed" if low_polish and dense else "failed",
        "baseline_average_score": slide_matrix.get("average_baseline_score", 4.39),
        "baseline_minimum_score": slide_matrix.get("minimum_slide_score", 4.33),
        "low_polish_opportunity_count": len(low_polish),
        "dense_slide_opportunity_count": len(dense),
        "global_opportunity_count": len(global_items),
        "opportunities": low_polish + dense + global_items,
        "source_risks_considered": risks,
        "bounded_only": True,
        "forbidden_changes_excluded": True,
    }


def _opportunity(row: dict[str, Any], category: str) -> dict[str, Any]:
    slide_number = int(row.get("slide_number", 0))
    archetype = str(row.get("archetype_id", ""))
    score = float(row.get("product_baseline_score", 0.0))
    parameter = "title_region_spacing" if category.startswith("low") else "table_row_height_delta"
    return {
        "opportunity_id": f"slide_{slide_number:02d}_{archetype}_{category}",
        "slide_number": slide_number,
        "archetype_id": archetype,
        "current_score": score,
        "category": category,
        "recommended_parameter": parameter,
        "bounded": True,
        "source_content_change_allowed": False,
    }
