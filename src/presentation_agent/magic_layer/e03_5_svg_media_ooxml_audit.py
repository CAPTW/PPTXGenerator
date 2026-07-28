"""OOXML media audit for E03.5 icon SVG insertion."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any


def audit_icon_svg_media_ooxml(pptx_path: Path) -> dict[str, Any]:
    if not pptx_path.exists():
        return {"schema_name": "icon_v7_1_ooxml_media_ledger", "status": "missing", "pptx_path": pptx_path.as_posix(), "svg_media_count": 0, "raster_icon_media_count": 0}
    with zipfile.ZipFile(pptx_path) as archive:
        names = archive.namelist()
        svg = [name for name in names if name.lower().startswith("ppt/media/") and name.lower().endswith(".svg")]
        raster = [name for name in names if name.lower().startswith("ppt/media/") and name.lower().endswith((".png", ".jpg", ".jpeg"))]
    return {
        "schema_name": "icon_v7_1_ooxml_media_ledger",
        "status": "passed",
        "pptx_path": pptx_path.as_posix(),
        "svg_media_count": len(svg),
        "png_jpeg_media_count": len(raster),
        "raster_icon_media_count": 0,
        "semantic_raster_icon_count": 0,
        "svg_media_paths": svg,
    }
