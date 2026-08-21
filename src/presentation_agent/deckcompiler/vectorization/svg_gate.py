"""Security, portability, and complexity gates for generated SVG assets."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


ALLOWED_TAGS = frozenset(
    {
        "svg",
        "g",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "defs",
        "clipPath",
        "linearGradient",
        "radialGradient",
        "stop",
    }
)
FORBIDDEN_TAGS = frozenset({"script", "image", "foreignObject", "text", "use", "filter"})
MAX_SVG_BYTES = 1_000_000
MAX_PATH_COUNT = 512
MAX_POINT_COUNT = 20_000


def validate_svg(path: Path) -> dict[str, Any]:
    """Reject embedded raster, text, scripts, external references, and excessive SVGs."""

    text = path.read_text(encoding="utf-8")
    issues: list[str] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return {
            "status": "failed",
            "issues": [f"xml_parse_failed:{exc}"],
            "svg_path": path.as_posix(),
        }

    tags: list[str] = []
    path_count = 0
    point_count = 0
    for element in root.iter():
        tag = element.tag.split("}")[-1]
        tags.append(tag)
        if tag not in ALLOWED_TAGS:
            issues.append(f"unsupported_tag:{tag}")
        if tag in FORBIDDEN_TAGS:
            issues.append(f"forbidden_tag:{tag}")
        for key, value in element.attrib.items():
            local_key = key.split("}")[-1].lower()
            lowered = value.lower()
            if local_key.startswith("on"):
                issues.append(f"event_handler:{local_key}")
            if local_key in {"href", "src"}:
                issues.append(f"external_reference:{local_key}")
            if "url(" in lowered or "javascript:" in lowered or "data:image" in lowered:
                issues.append(f"unsafe_attribute:{local_key}")
        if tag == "path":
            path_count += 1
            point_count += _path_point_count(element.attrib.get("d", ""))
        elif tag in {"polyline", "polygon"}:
            point_count += len(
                re.findall(r"[-+]?(?:\d*\.\d+|\d+)", element.attrib.get("points", ""))
            ) // 2

    if root.tag.split("}")[-1] != "svg":
        issues.append("root_must_be_svg")
    if "viewBox" not in root.attrib:
        issues.append("missing_viewbox")
    if len(text.encode("utf-8")) > MAX_SVG_BYTES:
        issues.append("svg_byte_budget_exceeded")
    if path_count > MAX_PATH_COUNT:
        issues.append("path_count_budget_exceeded")
    if point_count > MAX_POINT_COUNT:
        issues.append("point_count_budget_exceeded")
    if "base64" in text.lower():
        issues.append("embedded_base64_forbidden")

    return {
        "status": "passed" if not issues else "failed",
        "issues": sorted(set(issues)),
        "svg_path": path.as_posix(),
        "svg_bytes": len(text.encode("utf-8")),
        "path_count": path_count,
        "point_count": point_count,
        "tags": sorted(set(tags)),
        "embedded_raster_count": sum(tag == "image" for tag in tags),
        "text_element_count": sum(tag == "text" for tag in tags),
        "external_reference_count": sum(
            issue.startswith(("external_reference", "unsafe_attribute"))
            for issue in issues
        ),
    }


def _path_point_count(data: str) -> int:
    numbers = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", data)
    return len(numbers) // 2


__all__ = ["validate_svg"]
