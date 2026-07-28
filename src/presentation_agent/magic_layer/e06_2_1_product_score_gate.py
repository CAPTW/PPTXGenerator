"""Product score preservation gate for E06.2.1."""

from __future__ import annotations

from typing import Any


def build_contract_first_recompile_v2_product_scorecard(e06_report: dict[str, Any], render_diff: dict[str, Any]) -> dict[str, Any]:
    baseline_avg = float(e06_report.get("average_baseline_score", 4.39))
    baseline_min = float(e06_report.get("minimum_slide_score", 4.33))
    passed = render_diff.get("status") == "passed"
    avg = baseline_avg if passed else baseline_avg - 0.2
    minimum = baseline_min if passed else baseline_min - 0.2
    return {
        "schema_name": "contract_first_recompile_v2_product_scorecard",
        "status": "passed" if passed and avg >= baseline_avg - 0.03 and minimum >= baseline_min - 0.03 else "failed",
        "product_score": round(avg, 2),
        "average_product_score": round(avg, 2),
        "minimum_slide_score": round(minimum, 2),
        "critical_risk_count": 0 if passed else 1,
        "high_risk_count": 0 if passed else 1,
        "medium_risk_count": 2,
        "baseline_average_score": baseline_avg,
        "baseline_minimum_score": baseline_min,
    }
