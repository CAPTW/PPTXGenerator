"""Detect generic placeholder SVGs that must not satisfy semantic roles."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


LITERAL_PLUS_ROLES = {"plus", "add", "expand"}
LITERAL_CIRCLE_ROLES = {"circle", "status_dot", "bullet"}
LITERAL_SQUARE_ROLES = {"square", "checkbox_empty"}


def detect_placeholder_svg(svg_path: Path, *, role: str) -> dict[str, Any]:
    text = svg_path.read_text(encoding="utf-8") if svg_path.exists() else ""
    reasons: list[str] = []
    try:
        root = ET.fromstring(text)
        valid_xml = True
    except ET.ParseError:
        root = None
        valid_xml = False
    if not valid_xml:
        reasons.append("invalid_xml")
    primitive_count = sum(text.count(f"<{tag}") for tag in ("path", "line", "polyline", "circle", "rect", "ellipse", "polygon"))
    circle_count = text.count("<circle")
    rect_count = text.count("<rect")
    path_ds = re.findall(r"d=[\"']([^\"']+)[\"']", text)
    has_horizontal = any(re.search(r"M\s*8\s+12\s*h\s*8|M\s*4\s+12\s*h\s*16|M\s*8\s+12\s*H\s*16", d) for d in path_ds)
    has_vertical = any(re.search(r"M\s*12\s+8\s*v\s*8|M\s*12\s+4\s*v\s*16|M\s*12\s+8\s*V\s*16", d) for d in path_ds)
    generic_plus = has_horizontal and has_vertical and role not in LITERAL_PLUS_ROLES
    generic_circle_shell = circle_count >= 1 and primitive_count <= 3 and role not in LITERAL_CIRCLE_ROLES | LITERAL_PLUS_ROLES
    generic_square_shell = rect_count >= 1 and primitive_count <= 3 and role not in LITERAL_SQUARE_ROLES
    if generic_plus:
        reasons.append("generic_plus")
    if generic_circle_shell:
        reasons.append("generic_circle_shell")
    if generic_square_shell:
        reasons.append("generic_square_shell")
    if primitive_count <= 1 and role not in LITERAL_PLUS_ROLES | LITERAL_CIRCLE_ROLES | LITERAL_SQUARE_ROLES:
        reasons.append("too_few_primitives_for_semantic_role")
    return {
        "schema_name": "generic_placeholder_svg_detection",
        "svg_path": svg_path.as_posix(),
        "role": role,
        "valid_xml": valid_xml,
        "primitive_count": primitive_count,
        "is_placeholder": bool(reasons),
        "reasons": reasons,
    }
