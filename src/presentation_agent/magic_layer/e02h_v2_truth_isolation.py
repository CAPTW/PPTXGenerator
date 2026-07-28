"""Truth-isolation gate for E02H-V2 holdout runs."""

from __future__ import annotations

from typing import Any


def build_truth_isolation_report(case_reports: list[dict[str, Any]]) -> dict[str, Any]:
    production_truth = []
    copied = []
    for report in case_reports:
        sources = set(report.get("production_input_sources", []))
        if "source_layer_truth" in sources or "expected_semantic_slots" in sources or "expected_native_components" in sources:
            production_truth.append(report.get("case_id"))
        if report.get("visible_truth_label_copied"):
            copied.append(report.get("case_id"))
    passed = not production_truth and not copied and all(report.get("source_layer_truth_used_for_scoring_only") for report in case_reports)
    return {
        "schema_name": "holdout_truth_isolation_report",
        "status": "passed" if passed else "failed",
        "source_layer_truth_used_for_production": bool(production_truth),
        "source_layer_truth_used_for_scoring_only": not production_truth,
        "truth_label_copy_violation_count": len(copied),
        "production_truth_case_ids": production_truth,
        "truth_label_copy_case_ids": copied,
        "case_count": len(case_reports),
        "canva_parity_claimed": False,
    }
