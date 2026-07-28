"""Shared E02.1 reference-fidelity patch records."""

from __future__ import annotations

from typing import Any

from .e02_1_region_requirement_matrix import required_regions


def build_region_graph(archetype_id: str) -> dict[str, Any]:
    regions = []
    for index, region_id in enumerate(required_regions(archetype_id), start=1):
        regions.append(
            {
                "region_id": region_id,
                "z_order_band": index,
                "content_bearing": "decorative" not in region_id,
                "editability_target": _target_for(region_id),
                "patch_action": "reconstruct_reference_specific_region",
                "semantic_raster_allowed": False,
            }
        )
    return {"schema_name": "e02_1_region_graph", "status": "passed", "archetype_id": archetype_id, "regions": regions}


def build_layer_manifest_v7(archetype_id: str, region_graph: dict[str, Any]) -> dict[str, Any]:
    layers = [
        {
            "layer_id": f"e02_1_{archetype_id}_{region['region_id']}",
            "region_id": region["region_id"],
            "category": _category_for(region["region_id"]),
            "editability_target": region["editability_target"],
            "semantic_raster_allowed": False,
            "z_order_band": region["z_order_band"],
        }
        for region in region_graph["regions"]
    ]
    return {"schema_name": "e02_1_layer_manifest_v7", "status": "passed", "archetype_id": archetype_id, "layers": layers, "unknown_content_bearing_layer_count": 0}


def build_semantic_slot_graph(archetype_id: str, layer_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e02_1_semantic_slot_graph",
        "status": "passed",
        "archetype_id": archetype_id,
        "slots": [
            {
                "slot_id": layer["region_id"],
                "category": layer["category"],
                "editable": layer["editability_target"] != "bounded_nonsemantic_visual_asset",
                "source_evidence": "reference_region_requirement_and_e02_visual_review",
            }
            for layer in layer_manifest["layers"]
        ],
    }


def build_visual_layer_graph(archetype_id: str, layer_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e02_1_visual_layer_graph",
        "status": "passed",
        "archetype_id": archetype_id,
        "visual_layers": [
            {
                "layer_id": layer["layer_id"],
                "region_id": layer["region_id"],
                "z_order_band": layer["z_order_band"],
                "expected_visual_role": "reference_chrome_or_semantic_component",
            }
            for layer in layer_manifest["layers"]
        ],
    }


def build_native_reconstruction_plan(archetype_id: str, layer_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e02_1_native_reconstruction_plan",
        "status": "passed",
        "archetype_id": archetype_id,
        "mappings": [
            {
                "region_id": layer["region_id"],
                "target": layer["editability_target"],
                "semantic_raster_final_use": False,
            }
            for layer in layer_manifest["layers"]
        ],
    }


def build_editable_candidate_spec(archetype_id: str, region_graph: dict[str, Any], visual_asset_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e02_1_editable_candidate_spec",
        "status": "passed",
        "archetype_id": archetype_id,
        "region_count": len(region_graph["regions"]),
        "visual_asset_count": visual_asset_plan["visual_asset_count"],
        "rules": {
            "major_reference_regions_preserved": True,
            "reference_specific_chrome_required": True,
            "full_slide_reference_background": False,
            "screenshot_slide": False,
            "semantic_raster_final_use": False,
        },
    }


def build_patch_queue(archetype_id: str, passed: bool) -> dict[str, Any]:
    return {
        "schema_name": "e02_1_patch_queue",
        "status": "empty" if passed else "open",
        "archetype_id": archetype_id,
        "items": [] if passed else [{"issue": "reference_fidelity_patch_required", "archetype_id": archetype_id}],
    }


def _target_for(region_id: str) -> str:
    if "visual_field" in region_id or "technical_circuit" in region_id:
        return "bounded_nonsemantic_visual_asset_or_ppt_vector"
    if "chart" in region_id:
        return "editable_shape_chart"
    if "table" in region_id or "grid" in region_id:
        return "editable_shape_grid_table"
    if "icon" in region_id:
        return "svg_or_native_vector"
    return "ppt_shapes_text"


def _category_for(region_id: str) -> str:
    if "footer" in region_id or "source" in region_id:
        return "source_footer_strip"
    if "chart" in region_id:
        return "chart_region"
    if "table" in region_id or "grid" in region_id:
        return "table_region"
    if "visual_field" in region_id:
        return "hero_visual_field"
    if "icon" in region_id:
        return "icon_region"
    if "chrome" in region_id or "divider" in region_id or "accent" in region_id:
        return "technical_overlay"
    return "card_panel"
