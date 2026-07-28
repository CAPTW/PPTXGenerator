"""Detect blank, text-label, and placeholder-shell SVG icons."""

from __future__ import annotations

import re
from typing import Any


def detect_svg_placeholder(
    *,
    svg_text: str,
    visible_pixel_count: int,
    non_background_pixel_ratio: float,
    glyph_area_ratio: float,
    edge_density: float,
) -> dict[str, Any]:
    lower = svg_text.lower()
    tag_counts = {
        "path": len(re.findall(r"<path\b", lower)),
        "line": len(re.findall(r"<line\b", lower)),
        "polyline": len(re.findall(r"<polyline\b", lower)),
        "polygon": len(re.findall(r"<polygon\b", lower)),
        "circle": len(re.findall(r"<circle\b", lower)),
        "ellipse": len(re.findall(r"<ellipse\b", lower)),
        "rect": len(re.findall(r"<rect\b", lower)),
        "text": len(re.findall(r"<text\b", lower)),
        "image": len(re.findall(r"<image\b", lower)),
    }
    visible_semantic_primitives = tag_counts["path"] + tag_counts["line"] + tag_counts["polyline"] + tag_counts["polygon"] + tag_counts["circle"] + tag_counts["ellipse"]
    rect_only = tag_counts["rect"] > 0 and visible_semantic_primitives == 0
    failures: list[str] = []
    if visible_pixel_count <= 0 or non_background_pixel_ratio < 0.002:
        failures.append("blank_render")
    if tag_counts["text"] > 0:
        failures.append("svg_text_element")
    if tag_counts["image"] > 0 or "base64," in lower:
        failures.append("raster_image_element")
    if re.search(r"\b(href|xlink:href)=['\"](https?:|file:|//)", lower):
        failures.append("external_reference")
    if rect_only:
        failures.append("generic_rounded_square_only")
    if glyph_area_ratio > 0.82 and rect_only:
        failures.append("placeholder_card_container")
    if glyph_area_ratio < 0.01:
        failures.append("glyph_area_too_small")
    if edge_density < 0.001:
        failures.append("edge_density_too_low")
    return {
        "tag_counts": tag_counts,
        "is_blank": "blank_render" in failures,
        "is_placeholder_box": "placeholder_card_container" in failures or "generic_rounded_square_only" in failures,
        "is_role_label_text": tag_counts["text"] > 0,
        "is_generic_rounded_square_only": rect_only,
        "placeholder_failures": failures,
        "placeholder_status": "passed" if not failures else "rejected",
    }
