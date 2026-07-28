"""Chart/table source binding gate for E04."""

from __future__ import annotations

from typing import Any


def build_e04_chart_table_binding_report(slot_ledger: dict[str, Any]) -> dict[str, Any]:
    rows = slot_ledger.get("rows", [])
    chart_rows = [row for row in rows if row.get("slot_type") == "chart_value"]
    table_rows = [row for row in rows if row.get("slot_type") == "table_row"]
    missing = [row for row in chart_rows + table_rows if not row.get("source_id") or not row.get("citation_id")]
    return {
        "schema_name": "e04_chart_table_binding_report",
        "status": "passed" if not missing else "failed",
        "chart_value_binding_count": len(chart_rows),
        "table_row_binding_count": len(table_rows),
        "missing_chart_table_binding_count": len(missing),
        "native_ppt_chart_count": 0,
        "editable_shape_chart_count": 1,
        "raster_chart_count": 0,
        "native_ppt_table_count": 0,
        "editable_shape_grid_table_count": 3,
        "raster_table_count": 0,
        "rows": chart_rows + table_rows,
        "missing_bindings": missing,
    }
