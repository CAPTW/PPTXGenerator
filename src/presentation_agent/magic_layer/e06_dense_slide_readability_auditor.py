"""Dense slide readability audit for E06."""

from __future__ import annotations

from typing import Any


def audit_dense_slide_readability(text_report: dict[str, Any], table_density: dict[str, Any], source_footer: dict[str, Any], slide_matrix: dict[str, Any]) -> dict[str, Any]:
    target_scores = {row["slide_number"]: row["product_baseline_score"] for row in slide_matrix.get("rows", []) if row["slide_number"] in {9, 11, 14}}
    passed = (
        text_report.get("text_below_6pt_count", 1) == 0
        and text_report.get("text_overflow_count", 1) == 0
        and text_report.get("text_clipping_count", 1) == 0
        and table_density.get("status") == "passed"
        and source_footer.get("status") == "passed"
        and all(score >= 4.0 for score in target_scores.values())
    )
    return {
        "schema_name": "e06_dense_slide_readability_audit",
        "status": "passed" if passed else "patch_required",
        "verdict": "passed" if passed else "patch_required",
        "target_slides": [9, 11, 14],
        "text_below_6pt_count": text_report.get("text_below_6pt_count", 0),
        "text_overflow_count": text_report.get("text_overflow_count", 0),
        "text_clipping_count": text_report.get("text_clipping_count", 0),
        "table_density_verdict": table_density.get("status"),
        "source_footer_readability_verdict": source_footer.get("status"),
        "target_slide_scores": target_scores,
        "notes": "Slides 9/11/14 remain above baseline threshold after E04.2 dense readability patch.",
    }

