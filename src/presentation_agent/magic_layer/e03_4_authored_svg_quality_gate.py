"""SVG quality gates for E03.4 authored and curated icons."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


PRIMITIVE_TAGS = {"path", "line", "polyline", "circle", "rect", "ellipse", "polygon"}


def validate_authored_svg_manifest_v7(manifest: dict[str, Any]) -> dict[str, Any]:
    rows = manifest.get("authored_svgs") or manifest.get("icons") or []
    passed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for row in rows:
        svg_path = Path(row.get("svg_path") or "")
        role_id = row.get("role_id") or row.get("role") or svg_path.stem
        text = svg_path.read_text(encoding="utf-8") if svg_path.exists() else ""
        failures = validate_svg_text(text, role_id=role_id)
        result = {**row, "role_id": role_id, "quality_failures": failures}
        if failures:
            failed.append(result)
        else:
            passed.append(result)
    return {
        "schema_name": "authored_svg_quality_report_v7",
        "status": "passed" if not failed else "failed",
        "authored_svg_count": len(rows),
        "passed_count": len(passed),
        "failed_count": len(failed),
        "semantic_raster_icon_count": 0,
        "blank_svg_count": sum("blank_svg" in row["quality_failures"] for row in failed),
        "generic_placeholder_count": sum("generic_placeholder_shape" in row["quality_failures"] for row in failed),
        "passed_icons": passed,
        "failed_icons": failed,
    }


def validate_svg_text(text: str, *, role_id: str) -> list[str]:
    failures: list[str] = []
    if not text.strip():
        return ["blank_svg"]
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return ["invalid_xml"]
    lowered = text.lower()
    if "<text" in lowered:
        failures.append("has_text_element")
    if "<image" in lowered or "base64" in lowered:
        failures.append("has_raster_image")
    non_namespace_text = lowered.replace("http://www.w3.org/2000/svg", "").replace("https://www.w3.org/2000/svg", "")
    if "http://" in non_namespace_text or "https://" in non_namespace_text:
        failures.append("has_external_reference")
    if "viewbox" not in lowered:
        failures.append("missing_viewbox")
    if "currentcolor" not in lowered:
        failures.append("not_currentcolor_compatible")
    primitives = _primitive_nodes(root)
    if not primitives:
        failures.append("no_visible_glyph_primitives")
    if _is_generic_placeholder(root, text, role_id):
        failures.append("generic_placeholder_shape")
    return failures


def is_generic_placeholder_svg(text: str, *, role_id: str) -> bool:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return False
    return _is_generic_placeholder(root, text, role_id)


def primitive_count(text: str) -> int:
    try:
        return len(_primitive_nodes(ET.fromstring(text)))
    except ET.ParseError:
        return 0


def _primitive_nodes(root: ET.Element) -> list[ET.Element]:
    return [node for node in root.iter() if _local_name(node.tag) in PRIMITIVE_TAGS]


def _is_generic_placeholder(root: ET.Element, text: str, role_id: str) -> bool:
    if role_id in {"plus", "add"}:
        return False
    primitives = _primitive_nodes(root)
    if len(primitives) == 1 and _local_name(primitives[0].tag) in {"circle", "rect", "ellipse"}:
        return True
    if len(primitives) <= 3 and _has_center_plus_shape(text):
        return True
    return False


def _has_center_plus_shape(text: str) -> bool:
    compact = re.sub(r"\s+", "", text.lower())
    path_vertical = (bool(re.search(r"m12(?:\.0)?,[0-9.]+v", compact)) or bool(re.search(r"m12(?:\.0)?[0-9.]+v", compact))) or (
        "x1=\"12\"" in compact and "x2=\"12\"" in compact
    )
    path_horizontal = (bool(re.search(r"m[0-9.]+,?12(?:\.0)?h", compact)) or ("m5" in compact and "h14" in compact)) or (
        "y1=\"12\"" in compact and "y2=\"12\"" in compact
    )
    return path_vertical and path_horizontal


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
