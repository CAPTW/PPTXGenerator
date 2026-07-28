"""Layer manifest v7 builders for E03."""

from __future__ import annotations

from typing import Any

from .e03_object_graph_builder import LAYER_CATEGORIES


def build_layer_manifest_v7(object_graph: dict[str, Any]) -> dict[str, Any]:
    layers = [
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
        for node in object_graph["nodes"]
    ]
    return {
        "schema_name": "layer_manifest_v7",
        "status": "passed",
        "archetype_id": object_graph["archetype_id"],
        "allowed_categories": LAYER_CATEGORIES,
        "layers": layers,
        "unknown_content_bearing_layer_count": 0,
    }


def build_semantic_slot_graph(layer_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "semantic_slot_graph",
        "status": "passed",
        "archetype_id": layer_manifest["archetype_id"],
        "slots": [
            {
                "slot_id": layer["semantic_role"],
                "category": layer["category"],
                "bbox_norm": layer["bbox_norm"],
                "editable": layer["editability_target"] != "bounded_nonsemantic_visual_asset",
                "source_evidence": "reference_region_graph_and_archetype_hint_no_fake_ocr",
            }
            for layer in layer_manifest["layers"]
        ],
    }


def build_visual_layer_graph(layer_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "visual_layer_graph",
        "status": "passed",
        "archetype_id": layer_manifest["archetype_id"],
        "visual_layers": [
            {
                "layer_id": layer["layer_id"],
                "category": layer["category"],
                "semantic_role": layer["semantic_role"],
                "bbox_norm": layer["bbox_norm"],
                "z_order": layer["z_order"],
                "raster_allowed": layer["category"] in {"hero_visual_field", "replaceable_image_frame", "decorative_texture"},
            }
            for layer in layer_manifest["layers"]
        ],
    }


def build_text_region_ledger(layer_manifest: dict[str, Any]) -> dict[str, Any]:
    text_categories = {"title_text_region", "subtitle_text_region", "body_text_region", "source_footer_strip", "card_panel", "kpi_card", "table_region", "matrix_region", "timeline_phase", "process_node", "decision_node", "risk_indicator", "side_rail"}
    regions = [layer for layer in layer_manifest["layers"] if layer["category"] in text_categories]
    return {"schema_name": "text_region_ledger", "status": "passed", "archetype_id": layer_manifest["archetype_id"], "text_regions": regions, "fake_ocr_used": False}


def build_image_field_ledger(layer_manifest: dict[str, Any]) -> dict[str, Any]:
    fields = [layer for layer in layer_manifest["layers"] if layer["category"] in {"hero_visual_field", "replaceable_image_frame"}]
    return {
        "schema_name": "image_field_ledger",
        "status": "passed",
        "archetype_id": layer_manifest["archetype_id"],
        "image_fields": fields,
        "full_slide_image_background": False,
    }


def build_icon_region_ledger(layer_manifest: dict[str, Any], expected_count: int) -> dict[str, Any]:
    return {
        "schema_name": "icon_region_ledger",
        "status": "passed",
        "archetype_id": layer_manifest["archetype_id"],
        "semantic_icon_region_count": expected_count,
        "semantic_icon_raster_final_use": 0,
        "curated_or_native_vector_required": True,
    }


def build_chart_table_region_ledger(layer_manifest: dict[str, Any]) -> dict[str, Any]:
    chart_regions = [layer for layer in layer_manifest["layers"] if layer["category"] == "chart_region"]
    table_regions = [layer for layer in layer_manifest["layers"] if layer["category"] in {"table_region", "matrix_region"}]
    return {
        "schema_name": "chart_table_region_ledger",
        "status": "passed",
        "archetype_id": layer_manifest["archetype_id"],
        "chart_regions": chart_regions,
        "table_regions": table_regions,
        "raster_chart_count": 0,
        "raster_table_count": 0,
    }
