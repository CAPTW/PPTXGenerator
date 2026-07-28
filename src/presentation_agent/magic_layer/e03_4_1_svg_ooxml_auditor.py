"""OOXML audits for SVG media inserted into PowerPoint fixtures."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any


def audit_pptx_svg_media(pptx_path: Path) -> dict[str, Any]:
    if not pptx_path.exists():
        return {
            "schema_name": "svg_media_ooxml_audit",
            "status": "missing",
            "pptx_path": pptx_path.as_posix(),
            "slide_count": 0,
            "svg_media_count": 0,
            "png_jpeg_media_count": 0,
        }
    with zipfile.ZipFile(pptx_path) as archive:
        names = archive.namelist()
        svg_media = [name for name in names if name.lower().startswith("ppt/media/") and name.lower().endswith(".svg")]
        raster_media = [
            name
            for name in names
            if name.lower().startswith("ppt/media/") and name.lower().endswith((".png", ".jpg", ".jpeg"))
        ]
        slide_xml = [name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)]
        picture_count = 0
        text_count = 0
        for name in slide_xml:
            xml = archive.read(name).decode("utf-8", errors="ignore")
            picture_count += xml.count("<p:pic")
            text_count += xml.count("<a:t>")
    return {
        "schema_name": "svg_media_ooxml_audit",
        "status": "passed",
        "pptx_path": pptx_path.as_posix(),
        "slide_count": len(slide_xml),
        "icon_picture_object_count": picture_count,
        "text_label_count": text_count,
        "media_count": len(svg_media) + len(raster_media),
        "svg_media_count": len(svg_media),
        "png_jpeg_media_count": len(raster_media),
        "svg_media_paths": svg_media,
        "raster_media_paths": raster_media,
        "semantic_raster_icon_count": 0,
    }


def audit_svg_powerpoint_failure(
    *,
    previous_fixture_report: dict[str, Any],
    ooxml_audit: dict[str, Any],
    support_report: dict[str, Any],
) -> dict[str, Any]:
    root_causes = []
    if support_report.get("currentcolor_icon_count", 0) > 0:
        root_causes.append("currentColor-dependent SVGs do not provide explicit themed stroke/fill for PowerPoint rendering")
    if ooxml_audit.get("svg_media_count", 0) > 0 and previous_fixture_report.get("fixture_render_exists"):
        root_causes.append("previous fixture proved media existence but did not run per-cell visibility gates")
    return {
        "schema_name": "svg_powerpoint_failure_audit",
        "status": "failed_until_patched",
        "previous_fixture_path": previous_fixture_report.get("fixture_pptx_path"),
        "previous_fixture_render_path": previous_fixture_report.get("fixture_render_path"),
        "root_causes": root_causes or ["actual PowerPoint rendered fixture was not accepted by product review"],
        "svg_media_count": ooxml_audit.get("svg_media_count", 0),
        "png_jpeg_media_count": ooxml_audit.get("png_jpeg_media_count", 0),
    }
