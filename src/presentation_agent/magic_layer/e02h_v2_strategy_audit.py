"""Observed strategy audit for E02H-V2 holdouts."""

from __future__ import annotations

from typing import Any


FORBIDDEN_STRATEGIES = {"text_lift_overlay_baseline", "raster_page_baseline"}


def audit_holdout_strategies(case_reports: list[dict[str, Any]]) -> dict[str, Any]:
    forbidden = [row for row in case_reports if row.get("actual_strategy") in FORBIDDEN_STRATEGIES]
    unknown = [row for row in case_reports if row.get("actual_strategy") == "unknown_or_mixed"]
    return {
        "schema_name": "e02h_v2_actual_strategy_classification_report",
        "status": "passed" if not forbidden and not unknown else "failed",
        "case_count": len(case_reports),
        "text_lift_overlay_reclassified_count": sum(1 for row in case_reports if row.get("actual_strategy") == "text_lift_overlay_baseline"),
        "raster_page_reclassified_count": sum(1 for row in case_reports if row.get("actual_strategy") == "raster_page_baseline"),
        "unknown_or_mixed_count": len(unknown),
        "cases": [{"case_id": row.get("case_id"), "actual_strategy": row.get("actual_strategy")} for row in case_reports],
        "canva_parity_claimed": False,
    }
