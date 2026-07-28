"""Orchestration helpers for E03H-P2 SVG provenance rebinding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e03h_p2_candidate_recompiler import recompile_e03h_p2_reference_candidate
from src.presentation_agent.magic_layer.e03h_p2_pack_compiler import compile_e03h_p2_svg_rebound_pack
from src.presentation_agent.magic_layer.e03h_p2_semantic_icon_inventory import build_e03h_p2_semantic_icon_rebinding_inventory
from src.presentation_agent.magic_layer.e03h_p2_svg_resolver import resolve_e03h_p2_semantic_icons


def build_e03h_p2_rebinding_plan(e03h_p_root: str | Path, svg01_root: str | Path) -> dict[str, Any]:
    inventory = build_e03h_p2_semantic_icon_rebinding_inventory(e03h_p_root)
    resolution = resolve_e03h_p2_semantic_icons(inventory, svg01_root)
    return {
        "schema_name": "svg_rebinding_plan",
        "status": "passed" if inventory["status"] == "passed" and resolution["status"] == "passed" else "failed",
        "insertion_mode": "NATIVE_PATH_CONVERSION",
        "required_semantic_icon_count": inventory["required_semantic_icon_count"],
        "required_semantic_icon_svg_bound_coverage": resolution["required_semantic_icon_svg_bound_coverage"],
        "raster_fallback_allowed": False,
        "empty_circle_placeholder_allowed": False,
        "canva_parity_claimed": False,
    }


def run_reference_rebinding(reference_id: str, e03h_p_root: Path, output_root: Path, resolved_icons: list[dict[str, Any]]) -> dict[str, Any]:
    return recompile_e03h_p2_reference_candidate(reference_id, e03h_p_root / "references" / reference_id, output_root / "references" / reference_id, resolved_icons)


def run_pack_rebinding(e03h_p_root: Path, output_root: Path, resolutions_by_reference: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return compile_e03h_p2_svg_rebound_pack(
        e03h_p_root / "editable_hybrid_reference_pack_p2.pptx",
        output_root,
        resolutions_by_reference,
        original_contact_sheet=e03h_p_root / "editable_hybrid_reference_pack_p2_contact_sheet.png",
    )
