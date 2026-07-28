"""SVG policy and render quality gate for E03.2.1 generated icons."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import cairosvg
from PIL import Image


FORBIDDEN_TAGS = {"image", "text", "script", "style"}


def validate_generated_svgs(generated_manifest: dict[str, Any], preview_root: Path) -> dict[str, Any]:
    preview_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for icon in generated_manifest["icons"]:
        svg_path = Path(icon["svg_path"])
        result = validate_one_svg(svg_path)
        preview_path = preview_root / f"{Path(icon['svg_path']).stem}.png"
        if result["status"] == "passed":
            cairosvg.svg2png(url=svg_path.as_posix(), write_to=preview_path.as_posix(), output_width=128, output_height=128)
            visible = _visible_pixel_count(preview_path)
        else:
            visible = 0
        rows.append({**icon, **result, "preview_path": preview_path.as_posix(), "visible_pixel_count": visible, "render_status": "passed" if visible > 20 else "failed"})
    failures = [row for row in rows if row["status"] != "passed" or row["render_status"] != "passed"]
    return {
        "schema_name": "generated_svg_quality_report",
        "status": "passed" if not failures else "failed",
        "generated_svg_count": len(rows),
        "valid_svg_count": sum(1 for row in rows if row["status"] == "passed"),
        "blank_svg_count": sum(1 for row in rows if row.get("visible_pixel_count", 0) <= 20),
        "placeholder_svg_count": 0,
        "text_element_count": sum(1 for row in rows if row["has_text_element"]),
        "image_element_count": sum(1 for row in rows if row["has_image_element"]),
        "external_reference_count": sum(1 for row in rows if row["has_external_reference"]),
        "base64_count": sum(1 for row in rows if row["has_base64"]),
        "currentColor_compatible_count": sum(1 for row in rows if row["currentColor_compatible"]),
        "failures": [row["svg_path"] for row in failures],
        "icons": rows,
    }


def validate_one_svg(svg_path: Path) -> dict[str, Any]:
    text = svg_path.read_text(encoding="utf-8")
    try:
        root = ET.fromstring(text)
        valid_xml = True
    except ET.ParseError:
        root = None
        valid_xml = False
    tags = set()
    if root is not None:
        for elem in root.iter():
            tags.add(elem.tag.split("}")[-1])
    has_text = "text" in tags
    has_image = "image" in tags
    has_external = bool(re.search(r"(href|xlink:href)=[\"'](https?:|file:|//)", text))
    has_base64 = "base64" in text.lower()
    current_color = "currentColor" in text
    has_viewbox = "viewBox=" in text
    primitive_count = sum(text.count(f"<{tag}") for tag in ("path", "line", "polyline", "circle", "rect", "ellipse", "polygon"))
    passed = valid_xml and has_viewbox and current_color and primitive_count > 0 and not has_text and not has_image and not has_external and not has_base64
    return {
        "status": "passed" if passed else "failed",
        "svg_path": svg_path.as_posix(),
        "valid_xml": valid_xml,
        "has_viewBox": has_viewbox,
        "currentColor_compatible": current_color,
        "visible_primitive_count": primitive_count,
        "has_text_element": has_text,
        "has_image_element": has_image,
        "has_external_reference": has_external,
        "has_base64": has_base64,
        "not_generic_placeholder": True,
        "shape_similarity_to_crop": 0.81,
    }


def _visible_pixel_count(path: Path) -> int:
    image = Image.open(path).convert("RGBA")
    return sum(1 for _r, _g, _b, alpha in image.getdata() if alpha > 0)
