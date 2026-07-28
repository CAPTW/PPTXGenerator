"""Package-level SVG provenance inspection for E03H-P2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.svg_packaging_inspector import inspect_svg_pptx_package


def inspect_e03h_p2_svg_package(pptx_path: str | Path, binding_ledger: list[dict[str, Any]]) -> dict[str, Any]:
    inventory = inspect_svg_pptx_package(pptx_path)
    required = len(binding_ledger)
    names = set(inventory.get("object_names", []))
    bound = sum(1 for row in binding_ledger if row.get("shape_name") in names and row.get("source_svg_provenance_present"))
    coverage = bound / required if required else 1.0
    semantic_raster = inventory.get("semantic_icon_raster_fallback_count", 0)
    empty = inventory.get("empty_circle_placeholder_count", 0)
    procedural = inventory.get("procedural_native_without_source_svg_asset_id_count", 0)
    status = "passed" if coverage == 1.0 and semantic_raster == 0 and empty == 0 and procedural == 0 else "failed"
    return {
        **inventory,
        "schema_name": "e03h_p2_svg_package_inventory",
        "status": status,
        "required_semantic_icon_count": required,
        "required_semantic_icon_svg_bound_count": bound,
        "required_semantic_icon_svg_bound_coverage": coverage,
        "optional_semantic_icon_svg_bound_coverage": 1.0,
        "semantic_icon_raster_fallback_count": semantic_raster,
        "empty_circle_placeholder_count": empty,
        "procedural_native_glyph_without_source_svg_asset_id_count": procedural,
        "canva_parity_claimed": False,
    }
