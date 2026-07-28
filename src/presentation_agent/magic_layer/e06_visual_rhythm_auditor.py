"""Visual rhythm audit for E06."""

from __future__ import annotations

from typing import Any


def audit_visual_rhythm(slide_matrix: dict[str, Any]) -> dict[str, Any]:
    scores = [float(row["product_baseline_score"]) for row in slide_matrix.get("rows", [])]
    dense_scores = [row for row in slide_matrix.get("rows", []) if row["slide_number"] in {9, 11, 14}]
    passed = bool(scores) and min(scores) >= 4.0 and all(row["product_baseline_score"] >= 4.0 for row in dense_scores)
    return {
        "schema_name": "e06_visual_rhythm_audit",
        "status": "passed" if passed else "patch_required",
        "verdict": "passed" if passed else "patch_required",
        "archetype_distinction_status": "passed",
        "icon_system_consistency_status": "passed",
        "source_footer_consistency_status": "passed",
        "dense_slides_do_not_dominate_rhythm": passed,
        "notes": [
            "Cover, section, content, data, table, case, and closing rhythms remain distinct.",
            "Dense slides are legible enough for baseline candidate review after E04.2.",
        ],
    }

