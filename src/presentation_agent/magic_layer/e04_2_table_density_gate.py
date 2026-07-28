"""Table density gate for E04.2."""

from __future__ import annotations

from typing import Any


def build_e04_2_table_density_report(text_report: dict[str, Any], slide_reports: dict[int, dict[str, Any]]) -> dict[str, Any]:
    target_rows = [row for row in text_report.get("rows", []) if row.get("target_slide")]
    target_below = sum(int(row.get("text_below_6pt_count", 0)) for row in target_rows)
    return {
        "schema_name": "e04_2_table_density_report",
        "status": "passed" if target_below == 0 and all(report.get("status") == "passed" for report in slide_reports.values()) else "failed",
        "verdict": "passed" if target_below == 0 else "patch_required",
        "target_text_below_6pt_count": target_below,
        "patched_slide_count": len(slide_reports),
        "dense_data_strategy": "raised editable text minimums while retaining shape-grid components and source bindings",
        "slide_reports": slide_reports,
    }

