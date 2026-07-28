"""Inspect E04H source-bound deck package for SVG provenance and native objects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.svg_packaging_inspector import inspect_svg_pptx_package


def inspect_e04h_source_deck_package(pptx_path: str | Path, svg_binding_ledger: list[dict[str, Any]]) -> dict[str, Any]:
    inventory = inspect_svg_pptx_package(pptx_path)
    names = set(inventory.get("object_names", []))
    required = len(svg_binding_ledger)
    bound = sum(1 for row in svg_binding_ledger if row.get("shape_name") in names and row.get("source_svg_provenance_present"))
    coverage = bound / required if required else 1.0
    status = "passed" if coverage == 1.0 and inventory["semantic_icon_raster_fallback_count"] == 0 and inventory["empty_circle_placeholder_count"] == 0 and inventory["procedural_native_without_source_svg_asset_id_count"] == 0 else "failed"
    return {
        **inventory,
        "schema_name": "source_deck_svg_package_proof_report",
        "status": status,
        "required_semantic_icon_count": required,
        "required_semantic_icon_svg_bound_count": bound,
        "required_semantic_icon_svg_bound_coverage": coverage,
        "semantic_icon_raster_fallback_count": inventory["semantic_icon_raster_fallback_count"],
        "empty_circle_placeholder_count": inventory["empty_circle_placeholder_count"],
        "procedural_native_glyph_without_source_svg_asset_id_count": inventory["procedural_native_without_source_svg_asset_id_count"],
        "svg_provenance_survives_deck_compilation": status == "passed",
        "canva_parity_claimed": False,
    }
