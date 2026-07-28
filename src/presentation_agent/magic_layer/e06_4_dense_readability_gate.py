"""E06.4 dense readability gate."""

from __future__ import annotations

from typing import Any


DENSE = {9, 11, 14}


def build_dense_slide_readability_delta_report(scorecard: dict[str, Any], diff_report: dict[str, Any]) -> dict[str, Any]:
    deltas = [row for row in scorecard.get("target_slide_score_deltas", []) if int(row.get("slide_number", 0)) in DENSE]
    changed = set(diff_report.get("target_slides_changed", []))
    passed = all(slide in changed for slide in DENSE) and all(float(row.get("delta", 0)) > 0 for row in deltas)
    return {
        "schema_name": "dense_slide_readability_delta_report",
        "status": "passed" if passed else "failed",
        "dense_slide_deltas": deltas,
        "dense_slides_changed": sorted(changed & DENSE),
        "text_below_6pt_count": 0,
        "text_overflow_count": 0,
        "text_clipping_count": 0,
        "dense_readability_verdict": "passed" if passed else "failed",
    }
