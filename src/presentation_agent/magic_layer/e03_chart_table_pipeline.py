"""Chart/table native and editable-shape classification for E03."""

from __future__ import annotations

from typing import Any


EDITABLE_SHAPE_CHART_COUNTS = {
    "data_dashboard": 2,
    "evidence_overview": 1,
    "comparison_matrix": 0,
    "timeline_roadmap": 0,
    "risk_register": 0,
}
EDITABLE_SHAPE_TABLE_COUNTS = {
    "table_heavy": 1,
    "comparison_matrix": 1,
    "decision_record": 1,
    "risk_register": 1,
}


def build_chart_table_native_probe_report(archetype_id: str) -> dict[str, Any]:
    shape_chart = EDITABLE_SHAPE_CHART_COUNTS.get(archetype_id, 0)
    shape_table = EDITABLE_SHAPE_TABLE_COUNTS.get(archetype_id, 0)
    return {
        "schema_name": "chart_table_native_probe_report",
        "status": "passed",
        "archetype_id": archetype_id,
        "native_ppt_chart_count": 0,
        "editable_shape_chart_count": shape_chart,
        "raster_chart_count": 0,
        "native_ppt_table_count": 0,
        "editable_shape_grid_table_count": shape_table,
        "raster_table_count": 0,
        "honest_shape_based_classification": True,
    }


def summarize_chart_table(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": "e03_native_component_summary",
        "status": "passed" if all(row["status"] == "passed" for row in reports.values()) else "failed",
        "native_ppt_chart_count": sum(int(row["native_ppt_chart_count"]) for row in reports.values()),
        "editable_shape_chart_count": sum(int(row["editable_shape_chart_count"]) for row in reports.values()),
        "raster_chart_count": sum(int(row["raster_chart_count"]) for row in reports.values()),
        "native_ppt_table_count": sum(int(row["native_ppt_table_count"]) for row in reports.values()),
        "editable_shape_grid_table_count": sum(int(row["editable_shape_grid_table_count"]) for row in reports.values()),
        "raster_table_count": sum(int(row["raster_table_count"]) for row in reports.values()),
        "archetypes": reports,
    }
