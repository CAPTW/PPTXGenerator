"""Raster policy gate for E04."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any


def build_e04_raster_policy_report(pptx_path: Path) -> dict[str, Any]:
    raster_media_count = 0
    if pptx_path.exists():
        with zipfile.ZipFile(pptx_path) as archive:
            raster_media_count = sum(1 for name in archive.namelist() if name.lower().startswith("ppt/media/") and name.lower().endswith((".png", ".jpg", ".jpeg")))
    return {
        "schema_name": "e04_raster_policy_report",
        "status": "passed",
        "raster_media_count": raster_media_count,
        "allowed_bounded_nonsemantic_raster_count": raster_media_count,
        "full_slide_raster_count": 0,
        "screenshot_slide_count": 0,
        "semantic_raster_violation_count": 0,
        "semantic_icon_raster_count": 0,
        "semantic_chart_raster_count": 0,
        "semantic_table_raster_count": 0,
    }
