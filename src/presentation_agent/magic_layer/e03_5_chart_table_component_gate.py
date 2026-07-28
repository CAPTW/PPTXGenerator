from __future__ import annotations

from typing import Any


def build_chart_table_component_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ("native_ppt_chart_count", "editable_shape_chart_count", "raster_chart_count", "native_ppt_table_count", "editable_shape_grid_table_count", "raster_table_count")
    totals = {key: sum(int(row.get(key, 0) or 0) for row in rows) for key in keys}
    return {"schema_name": "e03_5_chart_table_component_summary", "status": "passed" if totals["raster_chart_count"] == 0 and totals["raster_table_count"] == 0 else "failed", **totals, "rows": rows}
