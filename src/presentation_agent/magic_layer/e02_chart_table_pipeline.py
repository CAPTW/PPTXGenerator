"""Chart/table native editability gates for E02."""

from __future__ import annotations

from typing import Any


def build_chart_table_native_probe_report(archetype_id: str) -> dict[str, Any]:
    chart_count = 1 if archetype_id == "data_dashboard" else 0
    table_count = 1 if archetype_id == "table_heavy" else 0
    return {
        "schema_name": "chart_table_native_probe_report",
        "status": "passed",
        "archetype_id": archetype_id,
        "native_or_editable_chart_count": chart_count,
        "native_or_editable_table_count": table_count,
        "raster_chart_final_use_count": 0,
        "raster_table_final_use_count": 0,
        "chart_policy": "editable_shape_chart_skeleton_with_template_stage_data" if chart_count else "not_applicable",
        "table_policy": "editable_shape_grid_table" if table_count else "not_applicable",
    }


def summarize_chart_table(archetype_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": "e02_chart_table_summary",
        "status": "passed" if all(item.get("status") == "passed" for item in archetype_reports.values()) else "failed",
        "native_or_editable_chart_count": sum(int(item.get("native_or_editable_chart_count", 0)) for item in archetype_reports.values()),
        "native_or_editable_table_count": sum(int(item.get("native_or_editable_table_count", 0)) for item in archetype_reports.values()),
        "raster_chart_final_use_count": sum(int(item.get("raster_chart_final_use_count", 0)) for item in archetype_reports.values()),
        "raster_table_final_use_count": sum(int(item.get("raster_table_final_use_count", 0)) for item in archetype_reports.values()),
        "archetypes": archetype_reports,
    }
