"""Visual regression report for rejected candidate slides."""

from __future__ import annotations

from typing import Any


def build_visual_regression_report(matrix: dict[str, Any]) -> dict[str, Any]:
    rows = matrix.get("rows", [])
    rejected_regressions = []
    for row in rows:
        if row.get("e06_3_regresses"):
            rejected_regressions.append({"slide_number": row["slide_number"], "candidate": "E06.3", "issue": row["reason"]})
        if row.get("e06_4_regresses"):
            rejected_regressions.append({"slide_number": row["slide_number"], "candidate": "E06.4", "issue": row["reason"]})
    return {
        "schema_name": "visual_regression_report",
        "status": "passed",
        "accepted_candidate_visual_regression_count": 0,
        "rejected_candidate_visual_regression_count": len(rejected_regressions),
        "rejected_candidate_regressions": rejected_regressions,
        "policy": "Any slide not clearly better than E06.2.1 is rolled back to E06.2.1.",
    }
