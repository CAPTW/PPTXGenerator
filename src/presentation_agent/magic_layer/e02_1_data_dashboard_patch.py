"""Data-dashboard specific E02.1 patch declaration."""

from __future__ import annotations


def data_dashboard_patch_actions() -> list[str]:
    return [
        "dense_kpi_row_with_icon_zones",
        "editable_shape_primary_chart",
        "editable_secondary_donut_insight_panel",
        "annotation_filter_source_strip",
        "dashboard_native_chrome",
    ]
