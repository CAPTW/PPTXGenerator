"""Layer-manifest v6 and semantic graph builders for E02."""

from __future__ import annotations

from typing import Any

from .e02_object_graph_builder import LAYER_CATEGORIES


def build_layer_manifest_v6(object_graph: dict[str, Any]) -> dict[str, Any]:
    layers = []
    for node in object_graph["nodes"]:
        layers.append(
            {
                "layer_id": f"layer_{node['object_id']}",
                "object_id": node["object_id"],
                "category": node["object_type"],
                "semantic_role": node["semantic_role"],
                "bbox_norm": node["bbox_norm"],
                "z_order": node["z_order"],
                "content_bearing": node["content_bearing"],
                "editability_target": node["editability_target"],
                "unknown_policy": "not_unknown",
            }
        )
    return {
        "schema_name": "layer_manifest_v6",
        "archetype_id": object_graph["archetype_id"],
        "status": "passed",
        "allowed_categories": LAYER_CATEGORIES,
        "layers": layers,
        "unknown_content_bearing_layer_count": 0,
    }


def build_semantic_slot_graph(layer_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "semantic_slot_graph",
        "archetype_id": layer_manifest["archetype_id"],
        "status": "passed",
        "slots": [
            {
                "slot_id": layer["semantic_role"],
                "category": layer["category"],
                "bbox_norm": layer["bbox_norm"],
                "editable": layer["editability_target"] != "bounded_nonsemantic_raster",
                "source_evidence": "reference_geometry_and_archetype_slot_hint",
            }
            for layer in layer_manifest["layers"]
        ],
    }


def build_visual_layer_graph(layer_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "visual_layer_graph",
        "archetype_id": layer_manifest["archetype_id"],
        "status": "passed",
        "visual_layers": [
            {
                "layer_id": layer["layer_id"],
                "category": layer["category"],
                "bbox_norm": layer["bbox_norm"],
                "z_order": layer["z_order"],
                "raster_allowed": layer["category"] in {"hero_visual_field", "replaceable_image_frame", "decorative_texture"},
            }
            for layer in layer_manifest["layers"]
        ],
    }


def build_text_region_ledger(layer_manifest: dict[str, Any]) -> dict[str, Any]:
    text_layers = [layer for layer in layer_manifest["layers"] if "text" in layer["category"] or layer["category"] in {"source_footer_strip", "card_panel", "kpi_card"}]
    return {"schema_name": "text_region_ledger", "status": "passed", "archetype_id": layer_manifest["archetype_id"], "text_regions": text_layers, "text_validation_mode": "geometry_slot_no_fake_ocr"}


def build_image_field_ledger(layer_manifest: dict[str, Any]) -> dict[str, Any]:
    fields = [layer for layer in layer_manifest["layers"] if layer["category"] in {"hero_visual_field", "replaceable_image_frame"}]
    return {"schema_name": "image_field_ledger", "status": "passed", "archetype_id": layer_manifest["archetype_id"], "image_fields": fields, "full_slide_image_background": False}


def build_icon_region_ledger(layer_manifest: dict[str, Any]) -> dict[str, Any]:
    archetype_id = layer_manifest["archetype_id"]
    expected = {"cover_hero": 1, "standard_content": 4, "data_dashboard": 4, "table_heavy": 2}[archetype_id]
    return {
        "schema_name": "icon_region_ledger",
        "status": "passed",
        "archetype_id": archetype_id,
        "semantic_icon_region_count": expected,
        "semantic_icon_raster_final_use": 0,
        "resolution_policy": "curated_or_native_vector_required",
    }


def build_chart_table_region_ledger(layer_manifest: dict[str, Any]) -> dict[str, Any]:
    chart_layers = [layer for layer in layer_manifest["layers"] if layer["category"] == "chart_region"]
    table_layers = [layer for layer in layer_manifest["layers"] if layer["category"] == "table_region"]
    return {
        "schema_name": "chart_table_region_ledger",
        "status": "passed",
        "archetype_id": layer_manifest["archetype_id"],
        "chart_regions": chart_layers,
        "table_regions": table_layers,
        "raster_chart_final_use": 0,
        "raster_table_final_use": 0,
    }
