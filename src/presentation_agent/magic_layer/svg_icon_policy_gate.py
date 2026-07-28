"""SVG policy validation for E01.3 generated icons."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


FORBIDDEN_TAGS = {"image", "text", "script", "style"}
VISIBLE_TAGS = {"path", "line", "polyline", "circle", "rect", "ellipse", "polygon"}


def validate_generated_svg_icons(manifest: dict[str, Any]) -> dict[str, Any]:
    records = []
    failures = []
    for item in manifest.get("generated_svgs") or []:
        path = Path(item["svg_path"])
        text = path.read_text(encoding="utf-8")
        try:
            root = ET.fromstring(text)
            valid_xml = True
        except ET.ParseError as exc:
            root = None
            valid_xml = False
            failures.append({"role_id": item["role_id"], "failure": "invalid_xml", "details": str(exc)})
        tags = set()
        if root is not None:
            for element in root.iter():
                tags.add(_local_name(element.tag))
        has_viewbox = root is not None and "viewBox" in root.attrib
        forbidden = sorted(tags & FORBIDDEN_TAGS)
        has_visible = bool(tags & VISIBLE_TAGS)
        has_external_ref = bool(re.search(r"\b(?:xlink:href|href)\s*=|url\(", text, flags=re.IGNORECASE))
        has_base64 = "base64" in text.lower()
        themed = "currentColor" in text or "stroke=" in text
        record = {
            "role_id": item["role_id"],
            "svg_path": item["svg_path"],
            "valid_xml": valid_xml,
            "has_viewBox": has_viewbox,
            "forbidden_tags": forbidden,
            "has_visible_primitives": has_visible,
            "has_external_reference": has_external_ref,
            "has_base64_bitmap": has_base64,
            "themeable": themed,
            "status": "passed",
        }
        for condition, failure in (
            (not has_viewbox, "missing_viewBox"),
            (bool(forbidden), "forbidden_tag"),
            (not has_visible, "no_visible_primitives"),
            (has_external_ref, "external_reference"),
            (has_base64, "base64_bitmap"),
            (not themed, "not_themeable"),
        ):
            if condition:
                record["status"] = "failed"
                failures.append({"role_id": item["role_id"], "failure": failure})
        records.append(record)
    return {
        "schema_name": "generated_svg_quality_report",
        "status": "passed" if not failures else "failed",
        "generated_svg_count": len(records),
        "failure_count": len(failures),
        "records": records,
        "failures": failures,
        "canva_parity_claimed": False,
    }


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag
