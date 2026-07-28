"""SVG normalization for the E01.5.1 curated Magic Layer icon pack."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


VISIBLE_TAGS = ("path", "line", "polyline", "polygon", "circle", "rect", "ellipse")


def normalize_svg_to_current_color(source_path: Path, target_path: Path) -> dict[str, Any]:
    source_text = source_path.read_text(encoding="utf-8", errors="ignore")
    text = normalize_svg_text(source_text)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(text, encoding="utf-8")
    policy = validate_svg_policy(text)
    return {
        "source_path": source_path.as_posix(),
        "target_path": target_path.as_posix(),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "normalized_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "viewBox": "0 0 24 24",
        "currentColor": "currentColor" in text,
        **policy,
    }


def normalize_svg_text(svg_text: str) -> str:
    text = svg_text.strip()
    text = re.sub(r"<\?xml[^>]*>\s*", "", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\s(width|height)=['\"][^'\"]+['\"]", "", text, count=2)
    if "viewBox=" in text:
        text = re.sub(r'viewBox=["\'][^"\']+["\']', 'viewBox="0 0 24 24"', text, count=1)
    else:
        text = text.replace("<svg", '<svg viewBox="0 0 24 24"', 1)
    if "xmlns=" not in text[:200]:
        text = text.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    text = _replace_color_attr(text, "stroke")
    text = _replace_color_attr(text, "fill")
    if "stroke-linecap" not in text:
        text = text.replace("<svg", '<svg stroke-linecap="round" stroke-linejoin="round"', 1)
    if "currentColor" not in text and "stroke=" not in text:
        text = text.replace("<svg", '<svg stroke="currentColor" fill="none"', 1)
    return text + "\n"


def validate_svg_policy(svg_text: str) -> dict[str, Any]:
    invalid_xml = False
    try:
        ET.fromstring(svg_text)
    except ET.ParseError:
        invalid_xml = True
    lower = svg_text.lower()
    visible = sum(len(re.findall(rf"<{tag}\b", lower)) for tag in VISIBLE_TAGS)
    failures = []
    if invalid_xml:
        failures.append("invalid_xml")
    if "viewbox=" not in lower:
        failures.append("missing_viewbox")
    if "<image" in lower or "base64," in lower:
        failures.append("contains_raster_image")
    if "<text" in lower:
        failures.append("contains_text")
    if "<script" in lower or re.search(r"\b(href|xlink:href)=['\"](https?:|file:|//)", lower):
        failures.append("contains_external_or_script_ref")
    if visible == 0:
        failures.append("no_visible_svg_primitives")
    if "currentcolor" not in lower:
        failures.append("not_currentcolor_compatible")
    return {
        "policy_status": "passed" if not failures else "failed",
        "policy_failures": failures,
        "visible_primitive_count": visible,
        "contains_image": "<image" in lower,
        "contains_text": "<text" in lower,
        "contains_external_ref": bool(re.search(r"\b(href|xlink:href)=['\"](https?:|file:|//)", lower)),
    }


def _replace_color_attr(text: str, attr: str) -> str:
    def repl(match: re.Match[str]) -> str:
        value = match.group(1).strip()
        if value.lower() in {"none", "transparent"}:
            return f'{attr}="{value}"'
        return f'{attr}="currentColor"'

    return re.sub(rf'{attr}=["\']([^"\']+)["\']', repl, text, flags=re.IGNORECASE)
