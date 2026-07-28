"""Renderable SVG glyph audit for curated Magic Layer icon libraries."""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from typing import Any

import cairosvg
from PIL import Image, ImageFilter

from .e01_5_2_svg_placeholder_detector import detect_svg_placeholder


RENDER_SIZES = [24, 48, 128, 256]


def render_svg_to_png(svg_path: Path, output_path: Path, *, size: int = 256, color: str = "#22D3EE") -> dict[str, Any]:
    svg_text = svg_path.read_text(encoding="utf-8", errors="ignore")
    render_text = _theme_svg(svg_text, color)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        png_bytes = cairosvg.svg2png(bytestring=render_text.encode("utf-8"), output_width=size, output_height=size)
        output_path.write_bytes(png_bytes)
        image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        return {"render_status": "rendered", "render_path": output_path.as_posix(), **measure_rendered_icon(image)}
    except Exception as exc:
        return {
            "render_status": "failed",
            "render_path": output_path.as_posix(),
            "render_error": f"{type(exc).__name__}: {exc}",
            "visible_pixel_count": 0,
            "non_background_pixel_ratio": 0.0,
            "bbox_of_visible_glyph": None,
            "glyph_area_ratio": 0.0,
            "edge_density": 0.0,
        }


def audit_svg_library(curated_root: Path, render_root: Path, *, schema_name: str) -> dict[str, Any]:
    records = []
    render_root.mkdir(parents=True, exist_ok=True)
    for svg_path in sorted(curated_root.glob("*.svg")):
        role = svg_path.stem
        svg_text = svg_path.read_text(encoding="utf-8", errors="ignore")
        rendered_sizes = {}
        quality = None
        for size in RENDER_SIZES:
            render = render_svg_to_png(svg_path, render_root / f"{role}_{size}.png", size=size)
            rendered_sizes[str(size)] = render
            if size == 256:
                quality = render
        assert quality is not None
        placeholder = detect_svg_placeholder(
            svg_text=svg_text,
            visible_pixel_count=quality["visible_pixel_count"],
            non_background_pixel_ratio=quality["non_background_pixel_ratio"],
            glyph_area_ratio=quality["glyph_area_ratio"],
            edge_density=quality["edge_density"],
        )
        failures = _policy_failures(svg_text, quality, placeholder)
        records.append(
            {
                "role": role,
                "source_path": svg_path.as_posix(),
                "sha256": hashlib.sha256(svg_path.read_bytes()).hexdigest(),
                "viewBox": _viewbox(svg_text),
                "element_counts": placeholder["tag_counts"],
                "has_text_element": placeholder["tag_counts"]["text"] > 0,
                "has_image_element": placeholder["tag_counts"]["image"] > 0,
                "has_external_reference": bool(re.search(r"\b(href|xlink:href)=['\"](https?:|file:|//)", svg_text.lower())),
                "uses_currentColor": "currentColor" in svg_text,
                "render_status": quality["render_status"],
                "render_width_height": [256, 256],
                "visible_pixel_count": quality["visible_pixel_count"],
                "non_background_pixel_ratio": quality["non_background_pixel_ratio"],
                "bbox_of_visible_glyph": quality["bbox_of_visible_glyph"],
                "glyph_area_ratio": quality["glyph_area_ratio"],
                "edge_density": quality["edge_density"],
                "is_blank": placeholder["is_blank"],
                "is_placeholder_box": placeholder["is_placeholder_box"],
                "is_role_label_text": placeholder["is_role_label_text"],
                "is_generic_rounded_square_only": placeholder["is_generic_rounded_square_only"],
                "is_duplicate_of_another_role": False,
                "render_quality_status": "passed" if not failures else "rejected",
                "quality_failures": failures,
                "rendered_sizes": rendered_sizes,
            }
        )
    return summarize_render_audit(schema_name, curated_root, records)


def summarize_render_audit(schema_name: str, curated_root: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": schema_name,
        "status": "passed" if all(record["render_quality_status"] == "passed" for record in records) else "patch_required",
        "curated_root": curated_root.as_posix(),
        "icon_count": len(records),
        "render_valid_count": sum(1 for record in records if record["render_quality_status"] == "passed"),
        "blank_svg_count": sum(1 for record in records if record["is_blank"]),
        "placeholder_svg_count": sum(1 for record in records if record["is_placeholder_box"]),
        "svg_text_label_violation_count": sum(1 for record in records if record["is_role_label_text"]),
        "image_element_count": sum(1 for record in records if record["has_image_element"]),
        "external_reference_count": sum(1 for record in records if record["has_external_reference"]),
        "currentColor_compatible_count": sum(1 for record in records if record["uses_currentColor"]),
        "records": records,
        "canva_parity_claimed": False,
    }


def measure_rendered_icon(image: Image.Image) -> dict[str, Any]:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    visible = sum(1 for value in alpha.tobytes() if value > 8)
    total = image.width * image.height
    if bbox is None:
        return {
            "visible_pixel_count": 0,
            "non_background_pixel_ratio": 0.0,
            "bbox_of_visible_glyph": None,
            "glyph_area_ratio": 0.0,
            "edge_density": 0.0,
        }
    bbox_area = max(1, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
    edges = alpha.filter(ImageFilter.FIND_EDGES)
    edge_pixels = sum(1 for value in edges.tobytes() if value > 16)
    return {
        "visible_pixel_count": visible,
        "non_background_pixel_ratio": round(visible / total, 6),
        "bbox_of_visible_glyph": list(bbox),
        "glyph_area_ratio": round(bbox_area / total, 6),
        "edge_density": round(edge_pixels / total, 6),
    }


def _policy_failures(svg_text: str, quality: dict[str, Any], placeholder: dict[str, Any]) -> list[str]:
    failures = list(placeholder["placeholder_failures"])
    lower = svg_text.lower()
    if quality["render_status"] != "rendered":
        failures.append("not_renderable")
    if "viewbox=" not in lower:
        failures.append("missing_viewbox")
    if "currentcolor" not in lower:
        failures.append("not_currentcolor_compatible")
    if quality["bbox_of_visible_glyph"] is not None:
        x0, y0, x1, y1 = quality["bbox_of_visible_glyph"]
        if x0 <= 0 or y0 <= 0 or x1 >= 256 or y1 >= 256:
            failures.append("glyph_touches_canvas_edge")
    return sorted(set(failures))


def _theme_svg(svg_text: str, color: str) -> str:
    text = svg_text.replace("currentColor", color)
    if "color:" not in text[:300]:
        text = text.replace("<svg", f'<svg color="{color}"', 1)
    return text


def _viewbox(svg_text: str) -> str | None:
    match = re.search(r'viewBox=["\']([^"\']+)["\']', svg_text)
    return match.group(1) if match else None
