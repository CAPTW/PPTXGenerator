"""Semantic and visual graph builders for E01."""

from __future__ import annotations

from typing import Any


def build_semantic_slot_graph(object_graph: dict[str, Any]) -> dict[str, Any]:
    slots = []
    for node in object_graph.get("nodes") or []:
        if node["semantic_role"] in {
            "title_text",
            "subtitle_text",
            "step_number_text",
            "step_heading_text",
            "step_body_text",
            "badge_text",
            "source_footer_text",
            "hero_visual_field",
            "checklist_panel",
            "card_panel",
            "semantic_icon",
            "technical_overlay",
        }:
            slots.append(
                {
                    "slot_id": f"slot_{node['object_id']}",
                    "object_id": node["object_id"],
                    "semantic_role": node["semantic_role"],
                    "bbox_norm": node["bbox_norm"],
                    "editability_target": node["editability_target"],
                    "text_content_policy": "placeholder_due_ocr_unavailable" if node["object_type"] == "text_region" else "not_text",
                    "accepted": True,
                    "rejected_reason": None,
                }
            )
    return {
        "schema_name": "semantic_slot_graph",
        "ocr_backend": "unavailable",
        "ocr_risk": "bounded_for_geometry_only_blocks_final_copy",
        "slots": slots,
        "identified_roles": sorted({slot["semantic_role"] for slot in slots}),
        "rejected_roles": [],
        "canva_parity_claimed": False,
    }


def build_visual_layer_graph(layer_manifest: dict[str, Any]) -> dict[str, Any]:
    nodes = [
        {
            "layer_id": layer["layer_id"],
            "layer_category": layer["layer_category"],
            "bbox_norm": layer["bbox_norm"],
            "z_order": layer["z_order"],
            "content_bearing": layer["content_bearing"],
        }
        for layer in layer_manifest.get("layers") or []
    ]
    return {
        "schema_name": "visual_layer_graph",
        "nodes": nodes,
        "relationships": [
            {"relationship_type": "above", "source": node["layer_id"], "target": "layer_background_base"}
            for node in nodes
            if node["layer_id"] != "layer_background_base"
        ],
        "visual_layer_count": len(nodes),
        "canva_parity_claimed": False,
    }
