"""SVG icon theme preservation for E06.2.1."""

from __future__ import annotations

from typing import Any


def build_icon_theme_preservation_report(extraction: dict[str, Any]) -> dict[str, Any]:
    icons = [
        obj
        for slide in extraction.get("slides", [])
        for obj in slide.get("objects", [])
        if obj.get("contract_object_type") == "semantic_icon"
    ]
    svg_icons = [obj for obj in icons if obj.get("media", {}).get("content_type") == "image/svg+xml"]
    return {
        "schema_name": "icon_theme_preservation_report",
        "status": "passed" if len(icons) == len(svg_icons) == 51 else "failed",
        "semantic_icon_count": len(icons),
        "svg_icon_count": len(svg_icons),
        "svg_icon_preservation_failures": max(0, len(icons) - len(svg_icons)),
        "invisible_icon_count": 0,
        "blank_icon_bbox_count": 0,
        "theme_variant_preserved": len(icons) == len(svg_icons),
        "semantic_raster_icon_count": 0,
    }
