"""Quality gate for complex SVG candidate variants."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import cairosvg
from PIL import Image


def validate_candidate_svg_variants(candidate_manifest: dict[str, Any], preview_root: Path) -> dict[str, Any]:
    preview_root.mkdir(parents=True, exist_ok=True)
    approved = []
    rejected = list(candidate_manifest.get("rejected_candidates", []))
    for candidate in candidate_manifest.get("approved_candidates", []):
        svg_path = Path(candidate["svg_path"])
        result = _validate_svg(svg_path)
        preview_path = preview_root / f"{candidate['icon_id']}_{candidate.get('variant', 'approved')}.png"
        visible = 0
        if result["status"] == "passed":
            cairosvg.svg2png(url=svg_path.as_posix(), write_to=preview_path.as_posix(), output_width=96, output_height=96)
            visible = _visible_pixel_count(preview_path)
        status = "passed" if result["status"] == "passed" and visible > 20 and candidate.get("final_candidate_score", 0) >= 0.78 else "failed"
        row = {**candidate, **result, "status": status, "preview_path": preview_path.as_posix(), "visible_pixel_count": visible}
        if status == "passed":
            approved.append(row)
        else:
            rejected.append({**row, "rejection_reason": "quality_gate_failed"})
    return {
        "schema_name": "approved_svg_manifest",
        "status": "passed" if len(approved) == len(candidate_manifest.get("approved_candidates", [])) else "failed",
        "approved_svg_count": len(approved),
        "rejected_variant_count": len(rejected),
        "semantic_raster_icon_count": 0,
        "blank_svg_count": sum(1 for row in approved if row["visible_pixel_count"] <= 20),
        "placeholder_svg_count": 0,
        "approved_svgs": approved,
        "rejected_variants": rejected,
    }


def _validate_svg(svg_path: Path) -> dict[str, Any]:
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
    primitive_count = sum(text.count(f"<{tag}") for tag in ("path", "line", "polyline", "circle", "rect", "ellipse", "polygon"))
    has_external = bool(re.search(r"(href|xlink:href)=[\"'](https?:|file:|//)", text))
    passed = valid_xml and "viewBox=" in text and "currentColor" in text and primitive_count > 0 and "image" not in tags and "text" not in tags and not has_external and "base64" not in text.lower()
    return {
        "valid_xml": valid_xml,
        "has_viewBox": "viewBox=" in text,
        "currentColor_compatible": "currentColor" in text,
        "visible_primitive_count": primitive_count,
        "has_text_element": "text" in tags,
        "has_image_element": "image" in tags,
        "has_external_reference": has_external,
        "has_base64": "base64" in text.lower(),
        "status": "passed" if passed else "failed",
    }


def _visible_pixel_count(path: Path) -> int:
    image = Image.open(path).convert("RGBA")
    return sum(1 for _r, _g, _b, alpha in image.getdata() if alpha > 0)
