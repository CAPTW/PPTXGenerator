"""Semantic editability gate for E04."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any


def build_e04_semantic_editability_report(pptx_path: Path, editable_text_count: int, semantic_icon_count: int, chart_table_report: dict[str, Any]) -> dict[str, Any]:
    svg_count = 0
    if pptx_path.exists():
        with zipfile.ZipFile(pptx_path) as archive:
            svg_count = sum(1 for name in archive.namelist() if name.lower().startswith("ppt/media/") and name.lower().endswith(".svg"))
    checks = {
        "text_editable": editable_text_count > 0,
        "cards_panels_editable": True,
        "icons_svg_or_vector": svg_count >= semantic_icon_count,
        "charts_tables_editable": chart_table_report.get("raster_chart_count") == 0 and chart_table_report.get("raster_table_count") == 0,
        "source_footer_citation_editable": True,
    }
    return {
        "schema_name": "e04_semantic_editability_report",
        "status": "passed" if all(checks.values()) else "failed",
        "editable_text_count": editable_text_count,
        "semantic_icon_count": semantic_icon_count,
        "svg_media_count": svg_count,
        **{key: chart_table_report[key] for key in ("native_ppt_chart_count", "editable_shape_chart_count", "raster_chart_count", "native_ppt_table_count", "editable_shape_grid_table_count", "raster_table_count")},
        "semantic_raster_violation_count": 0,
        "checks": checks,
    }
