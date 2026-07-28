"""Conservative SVG-source-to-PPT-native conversion planning."""

from __future__ import annotations

import hashlib
from typing import Any


def convert_svg_to_native_plan(asset: dict[str, Any]) -> dict[str, Any]:
    visible_count = int(asset.get("path_count", 0)) + int(asset.get("primitive_count", 0))
    failures = []
    if visible_count <= 0:
        failures.append("no_visible_svg_primitives")
    if not asset.get("canonical_viewbox"):
        failures.append("missing_viewbox")
    seed = f"{asset.get('asset_id')}|{asset.get('sha256')}|NATIVE_PATH_CONVERSION"
    conversion_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    return {
        "schema_name": "svg_native_path_conversion_plan",
        "status": "passed" if not failures else "failed",
        "source_svg_asset_id": asset.get("asset_id"),
        "source_svg_path": asset.get("source_path"),
        "source_svg_sha256": asset.get("sha256"),
        "conversion_hash": conversion_hash,
        "native_part_count": max(1, visible_count),
        "supported_svg_elements": ["path", "circle", "ellipse", "rect", "line", "polyline", "polygon", "simple_g"],
        "unsupported_svg_elements": [],
        "conversion_mode": "NATIVE_PATH_CONVERSION",
        "provenance_policy": "shape names carry source SVG asset ID and conversion hash",
        "failures": failures,
        "canva_parity_claimed": False,
    }
