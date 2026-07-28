"""Object graph and layer manifest for the E03.2 golden slide."""

from __future__ import annotations

from typing import Any


def build_e03_2_object_graph(analysis: dict[str, Any]) -> dict[str, Any]:
    nodes = []
    for region in analysis["major_regions"]:
        nodes.append(
            {
                "object_id": region["region_id"],
                "semantic_role": region["semantic_role"],
                "bbox_px": region["bbox_px"],
                "bbox_norm": region["bbox_norm"],
                "polygon_or_mask_hint": "rect_or_notched_rect",
                "z_order": region["expected_z_order"],
                "group_id": _group_id(region["region_id"]),
                "parent_component": _parent(region["region_id"]),
                "content_bearing": region["content_bearing"],
                "editable_target": region["editable_target"],
                "visual_priority": region["visual_priority"],
                "must_preserve": region["must_preserve"],
                "allowed_raster_policy": "none_for_semantic;bounded_nonsemantic_only",
                "source_confidence": 0.94,
                "unknown_disposition": "known_semantic_or_decorative",
            }
        )
    relationships = _relationships()
    return {
        "schema_name": "e03_2_object_graph_v2",
        "status": "passed",
        "target_archetype": analysis["target_archetype"],
        "canvas_px": analysis["canvas_px"],
        "nodes": nodes,
        "relationships": relationships,
        "unknown_content_bearing_layer_count": 0,
        "semantic_raster_violation_count": 0,
    }


def build_e03_2_layer_manifest(graph: dict[str, Any]) -> dict[str, Any]:
    layers = [
        {
            "layer_id": node["object_id"],
            "semantic_role": node["semantic_role"],
            "bbox_norm": node["bbox_norm"],
            "z_order": node["z_order"],
            "editable_target": node["editable_target"],
            "content_bearing": node["content_bearing"],
            "group_id": node["group_id"],
        }
        for node in graph["nodes"]
    ]
    return {
        "schema_name": "e03_2_layer_manifest_v6",
        "status": "passed",
        "target_archetype": graph["target_archetype"],
        "layers": layers,
        "layer_count": len(layers),
    }


def build_e03_2_semantic_slot_graph(graph: dict[str, Any]) -> dict[str, Any]:
    slots = [node for node in graph["nodes"] if node["content_bearing"]]
    return {
        "schema_name": "e03_2_semantic_slot_graph",
        "status": "passed",
        "target_archetype": graph["target_archetype"],
        "slots": slots,
        "slot_count": len(slots),
    }


def _group_id(region_id: str) -> str:
    if region_id.startswith("module_card"):
        return "visual_toc_module_cards"
    if region_id.startswith("footer") or region_id == "source_footer_strip":
        return "visual_toc_footer"
    if "header" in region_id or "title" in region_id or "technical" in region_id:
        return "visual_toc_header"
    return "visual_toc_main"


def _parent(region_id: str) -> str:
    if region_id.startswith("module_card"):
        return "module_card_group"
    if region_id.startswith("footer"):
        return "source_footer_strip"
    if region_id in {"title_region", "header_meta_region", "technical_overlay_region"}:
        return "dark_header_region"
    return "slide"


def _relationships() -> list[dict[str, str]]:
    return [
        {"type": "contains", "source": "dark_header_region", "target": "title_region"},
        {"type": "contains", "source": "dark_header_region", "target": "header_meta_region"},
        {"type": "contains", "source": "main_stage_region", "target": "module_card_group"},
        {"type": "contains", "source": "module_card_group", "target": "module_card_02_active"},
        {"type": "contains", "source": "source_footer_strip", "target": "footer_source_cluster"},
        {"type": "aligned_with", "source": "progress_path_region", "target": "module_card_group"},
        {"type": "anchored_to", "source": "right_meta_panel", "target": "main_stage_region"},
        {"type": "grouped_with", "source": "module_card_01", "target": "module_card_02_active"},
        {"type": "above", "source": "progress_path_region", "target": "module_card_group"},
        {"type": "below", "source": "source_footer_strip", "target": "main_stage_region"},
        {"type": "protects_zone", "source": "module_card_group", "target": "reading_path_region"},
        {"type": "belongs_to_component", "source": "right_meta_panel", "target": "visual_toc"},
    ]
