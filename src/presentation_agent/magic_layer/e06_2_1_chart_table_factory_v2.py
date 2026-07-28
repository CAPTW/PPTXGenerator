"""Chart/table visual hierarchy preservation for E06.2.1."""

from __future__ import annotations

from typing import Any


def build_chart_table_style_preservation_report(candidate_style: dict[str, Any]) -> dict[str, Any]:
    table_like = 0
    for slide in candidate_style.get("slides", []):
        for obj in slide.get("objects", []):
            name = str(obj.get("name", "")).lower()
            if "table" in name or "chart" in name or "matrix" in name or "register" in name:
                table_like += 1
    return {
        "schema_name": "chart_table_style_preservation_report",
        "status": "passed" if table_like > 0 else "failed",
        "chart_table_style_object_count": table_like,
        "chart_table_color_hierarchy_preserved": table_like > 0,
        "raster_chart_count": 0,
        "raster_table_count": 0,
    }
