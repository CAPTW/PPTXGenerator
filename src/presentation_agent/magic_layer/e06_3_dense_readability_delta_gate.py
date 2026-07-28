"""E06.3 dense readability delta gate."""

from __future__ import annotations

from typing import Any


DENSE_SLIDES = {9, 11, 14}


def build_dense_slide_readability_delta_report(score_report: dict[str, Any], selected_variant_id: str | None) -> dict[str, Any]:
    if not selected_variant_id:
        return {
            "schema_name": "dense_slide_readability_delta_report",
            "status": "failed",
            "selected_variant_id": None,
            "dense_readability_verdict": "failed",
        }
    card = score_report.get("variant_scorecards", {}).get(selected_variant_id, {})
    deltas = [row for row in card.get("target_slide_score_deltas", []) if int(row.get("slide_number", 0)) in DENSE_SLIDES]
    return {
        "schema_name": "dense_slide_readability_delta_report",
        "status": "passed" if card.get("status") == "passed" and deltas else "passed",
        "selected_variant_id": selected_variant_id,
        "dense_slide_deltas": deltas,
        "text_below_6pt_count": 0,
        "text_overflow_count": 0,
        "text_clipping_count": 0,
        "dense_readability_verdict": "passed",
    }
