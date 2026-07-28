"""Target slide tuning plan for E06.4."""

from __future__ import annotations

from typing import Any


TARGET_SLIDES = {
    2: "visual_toc",
    9: "comparison_matrix",
    10: "data_dashboard",
    11: "table_heavy",
    14: "risk_register",
}


def build_target_slide_tuning_plan(slide_matrix: dict[str, Any]) -> dict[str, Any]:
    rows = {int(row.get("slide_number", 0)): row for row in slide_matrix.get("rows", [])}
    targets = []
    for slide_number, archetype in TARGET_SLIDES.items():
        row = rows.get(slide_number, {})
        targets.append(
            {
                "slide_number": slide_number,
                "archetype_id": archetype,
                "baseline_score": row.get("product_baseline_score"),
                "human_tuning_goal": _goal(slide_number),
                "allowed_change_scope": "contract layout/style/icon/table parameters only",
                "source_content_change_allowed": False,
            }
        )
    return {
        "schema_name": "target_slide_tuning_plan",
        "status": "passed" if len(targets) == 5 else "failed",
        "target_slide_count": len(targets),
        "target_slides": targets,
        "non_target_slide_policy": "preserve unless shared rendering/candidate packaging requires no-op carryover",
    }


def _goal(slide_number: int) -> str:
    return {
        2: "Strengthen active/reading path hierarchy and module row scanability without darkening text.",
        9: "Open comparison matrix spacing and improve status-chip readability without reducing content contrast.",
        10: "Improve chart/insight hierarchy, KPI spacing, and primary data area clarity.",
        11: "Improve table header and row hierarchy while preserving dense table readability.",
        14: "Improve risk/status chip hierarchy and preserve source-bound register rows.",
    }[slide_number]
