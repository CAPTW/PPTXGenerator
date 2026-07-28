"""Table-heavy specific E02.1 patch declaration."""

from __future__ import annotations


def table_heavy_patch_actions() -> list[str]:
    return [
        "dense_editable_shape_grid_table",
        "header_icon_zones",
        "left_side_rail_icon_group",
        "bottom_kpi_note_strip",
        "premium_grid_chrome",
    ]
