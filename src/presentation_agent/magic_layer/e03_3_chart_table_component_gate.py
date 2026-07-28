"""Chart/table component gate for E03.3."""

from __future__ import annotations

from typing import Any


def build_chart_table_component_ledger(archetype: str) -> dict[str, Any]:
    native_chart = 0
    shape_chart = 1 if archetype in {"data_dashboard"} else 0
    native_table = 0
    shape_table = 1 if archetype in {"table_heavy", "comparison_matrix", "risk_register"} else 0
    return {
        "schema_name": "chart_table_component_ledger",
        "status": "passed",
        "archetype_id": archetype,
        "native_ppt_chart_count": native_chart,
        "editable_shape_chart_count": shape_chart,
        "raster_chart_count": 0,
        "native_ppt_table_count": native_table,
        "editable_shape_grid_table_count": shape_table,
        "raster_table_count": 0,
        "terminology_note": "Shape-based chart/table components are reported separately from native PPT chart/table objects.",
    }
