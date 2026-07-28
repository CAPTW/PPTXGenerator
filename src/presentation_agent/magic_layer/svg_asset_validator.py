"""Validate resolved SVG files for semantic icon use."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def validate_resolved_svg_assets(resolution_map: dict[str, Any], registry: dict[str, Any], repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root or Path.cwd()).resolve()
    assets_by_id = registry.get("assets_by_id") or {asset["asset_id"]: asset for asset in registry.get("assets", [])}
    validations = {}
    embedded_raster_count = 0
    external_dependency_count = 0
    invalid_required_count = 0
    for intent, resolution in resolution_map.get("resolutions", {}).items():
        asset_id = resolution.get("selected_svg_asset_id")
        asset = assets_by_id.get(asset_id)
        if not asset:
            invalid_required_count += 1
            validations[intent] = {"status": "failed", "reason": "missing_asset", "semantic_intent": intent}
            continue
        path = root / asset["source_path"]
        text = path.read_text(encoding="utf-8", errors="ignore")
        lower = text.lower()
        try:
            ET.fromstring(text)
            parse_ok = True
        except ET.ParseError:
            parse_ok = False
        has_raster = "<image" in lower or "data:image" in lower or "base64," in lower
        has_external = "<script" in lower or bool(re.search(r"\b(href|xlink:href)=['\"](https?:|file:|//)", lower))
        if has_raster:
            embedded_raster_count += 1
        if has_external:
            external_dependency_count += 1
        failures = []
        if not parse_ok:
            failures.append("xml_parse_failed")
        if has_raster:
            failures.append("embedded_raster_payload")
        if has_external:
            failures.append("external_dependency_or_script")
        if not asset.get("canonical_viewbox"):
            failures.append("missing_normalized_viewbox")
        if failures:
            invalid_required_count += 1
        validations[intent] = {
            "semantic_intent": intent,
            "status": "passed" if not failures else "failed",
            "asset_id": asset_id,
            "source_path": asset["source_path"],
            "parse_xml": parse_ok,
            "has_embedded_raster": has_raster,
            "has_external_dependency": has_external,
            "viewbox": asset.get("canonical_viewbox"),
            "recolor_feasible": asset.get("recolor_supported", False),
            "scale_to_fit_feasible": bool(asset.get("canonical_viewbox")),
            "failures": failures,
        }
    return {
        "schema_name": "svg_asset_validation_report",
        "status": "passed" if invalid_required_count == 0 else "failed",
        "validated_asset_count": len(validations),
        "embedded_raster_count": embedded_raster_count,
        "external_dependency_count": external_dependency_count,
        "invalid_required_count": invalid_required_count,
        "validations": validations,
        "canva_parity_claimed": False,
    }
