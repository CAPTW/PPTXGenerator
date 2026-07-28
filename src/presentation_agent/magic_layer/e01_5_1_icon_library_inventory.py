"""Raw SVG inventory for E01.5.1 curated icon library expansion."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def inventory_svg_sources(roots: list[Path]) -> dict[str, Any]:
    registry_hints = _load_generated_registry_hints(roots)
    records: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for svg_path in sorted(root.rglob("*.svg")):
            resolved = svg_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            text = svg_path.read_text(encoding="utf-8", errors="ignore")
            records.append(_record(svg_path, text, registry_hints))
    invalid = [record for record in records if record["text_element_usage"] or record["raster_image_element_usage"] or record["external_reference_usage"]]
    return {
        "schema_name": "raw_svg_inventory_expanded",
        "status": "passed",
        "source_roots": [root.as_posix() for root in roots],
        "raw_svg_count": len(records),
        "invalid_or_policy_risk_count": len(invalid),
        "records": records,
        "raw_source_files_modified": False,
        "canva_parity_claimed": False,
    }


def _record(svg_path: Path, text: str, registry_hints: dict[str, list[str]]) -> dict[str, Any]:
    role_hints = sorted(set([*_filename_hints(svg_path), *registry_hints.get(svg_path.as_posix(), [])]))
    return {
        "source_path": svg_path.as_posix(),
        "sha256": hashlib.sha256(svg_path.read_bytes()).hexdigest(),
        "viewBox": _attr(text, "viewBox"),
        "width": _attr(text, "width"),
        "height": _attr(text, "height"),
        "currentColor_support": "currentColor" in text,
        "stroke_usage": _attr(text, "stroke") or ("present" if "stroke=" in text else "none"),
        "fill_usage": _attr(text, "fill") or ("present" if "fill=" in text else "none"),
        "path_count": len(re.findall(r"<path\b", text)),
        "line_count": len(re.findall(r"<line\b", text)),
        "polyline_count": len(re.findall(r"<polyline\b", text)),
        "circle_count": len(re.findall(r"<circle\b", text)),
        "rect_count": len(re.findall(r"<rect\b", text)),
        "external_reference_usage": bool(re.search(r"\b(href|xlink:href)=['\"](https?:|file:|//)", text)),
        "text_element_usage": bool(re.search(r"<text\b", text)),
        "raster_image_element_usage": bool(re.search(r"<image\b", text)),
        "role_hints": role_hints,
        "renderability_status": "renderable_candidate" if "<svg" in text else "invalid_svg",
    }


def _attr(text: str, name: str) -> str | None:
    match = re.search(rf'{name}=["\']([^"\']+)["\']', text)
    return match.group(1) if match else None


def _filename_hints(path: Path) -> list[str]:
    stem = path.stem.lower().replace("tabler__", "").replace("-", "_")
    parts = [stem]
    if path.parent.name not in {"icons", "outline", "filled", "tabler", "normalized", "magic_layer"}:
        parts.append(path.parent.name.lower().replace("-", "_"))
    return parts


def _load_generated_registry_hints(roots: list[Path]) -> dict[str, list[str]]:
    hints: dict[str, list[str]] = {}
    for root in roots:
        registries = [root / "icon_registry.json"]
        if root.exists():
            registries.extend(root.rglob("icon_registry.json"))
        for registry in registries:
            if not registry.exists():
                continue
            try:
                data = json.loads(registry.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            for entry in data.get("icons", []):
                path = entry.get("generated_svg_path")
                if path:
                    hints.setdefault(path, []).append(entry.get("role_hint", "generated_observed_svg"))
    return hints
