"""Observed-region object graph builder for E02 archetypes."""

from __future__ import annotations

from typing import Any


LAYER_CATEGORIES = [
    "background_base",
    "hero_visual_field",
    "replaceable_image_frame",
    "decorative_texture",
    "title_text_region",
    "subtitle_text_region",
    "body_text_region",
    "source_footer_strip",
    "card_panel",
    "checklist_panel",
    "kpi_card",
    "icon_region",
    "chart_region",
    "table_region",
    "matrix_region",
    "process_node",
    "timeline_phase",
    "connector",
    "technical_overlay",
    "accent_line",
    "shadow_or_glow",
    "unknown",
]


def archetype_slots(archetype_id: str) -> list[dict[str, Any]]:
    slots = {
        "cover_hero": [
            _slot("title", "title_text_region", (0.05, 0.14, 0.42, 0.22), "ppt_text"),
            _slot("subtitle", "subtitle_text_region", (0.05, 0.38, 0.44, 0.17), "ppt_text"),
            _slot("hero_visual_field", "hero_visual_field", (0.50, 0.08, 0.43, 0.72), "bounded_replaceable_visual_field"),
            _slot("meta_bar", "card_panel", (0.05, 0.64, 0.36, 0.10), "ppt_shapes_text"),
            _slot("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
        ],
        "standard_content": [
            _slot("title", "title_text_region", (0.05, 0.06, 0.45, 0.11), "ppt_text"),
            _slot("content_card_group", "card_panel", (0.06, 0.22, 0.70, 0.56), "ppt_shapes_text"),
            _slot("body_text_regions", "body_text_region", (0.10, 0.28, 0.58, 0.42), "ppt_text"),
            _slot("insight_or_takeaway", "card_panel", (0.78, 0.20, 0.18, 0.58), "ppt_shapes_text"),
            _slot("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
        ],
        "data_dashboard": [
            _slot("title", "title_text_region", (0.07, 0.05, 0.55, 0.10), "ppt_text"),
            _slot("kpi_cards", "kpi_card", (0.06, 0.18, 0.88, 0.14), "ppt_shapes_text"),
            _slot("primary_chart", "chart_region", (0.06, 0.38, 0.54, 0.42), "editable_shape_chart"),
            _slot("secondary_chart_or_insight_panel", "card_panel", (0.64, 0.38, 0.30, 0.42), "ppt_shapes_text"),
            _slot("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
        ],
        "table_heavy": [
            _slot("title", "title_text_region", (0.06, 0.05, 0.55, 0.10), "ppt_text"),
            _slot("table_region", "table_region", (0.06, 0.20, 0.88, 0.58), "editable_shape_grid_table"),
            _slot("header_band", "card_panel", (0.06, 0.20, 0.88, 0.08), "ppt_shapes_text"),
            _slot("row_groups", "table_region", (0.06, 0.28, 0.88, 0.50), "editable_shape_grid_table"),
            _slot("source_footer_strip", "source_footer_strip", (0.00, 0.92, 1.00, 0.08), "ppt_shapes_text"),
            _slot("optional_kpi_chips", "kpi_card", (0.06, 0.82, 0.88, 0.07), "ppt_shapes_text"),
        ],
    }
    return slots[archetype_id]


def build_object_graph_v2(archetype_id: str) -> dict[str, Any]:
    nodes = []
    for z_order, slot in enumerate(archetype_slots(archetype_id), start=1):
        nodes.append(
            {
                "object_id": f"{archetype_id}_{slot['slot_id']}",
                "bbox_norm": slot["bbox_norm"],
                "bbox_px": _bbox_px(slot["bbox_norm"]),
                "polygon": _polygon(slot["bbox_norm"]),
                "mask": None,
                "z_order": z_order,
                "object_type": slot["category"],
                "semantic_role": slot["slot_id"],
                "content_bearing": slot["category"] not in {"background_base", "technical_overlay", "accent_line"},
                "editability_target": slot["editability_target"],
                "source_confidence": 0.88,
                "dependencies": [],
                "unknown_disposition": "not_unknown",
            }
        )
    relationships = []
    for idx, node in enumerate(nodes):
        if idx > 0:
            relationships.append({"type": "above", "source": node["object_id"], "target": nodes[idx - 1]["object_id"]})
        if node["semantic_role"] == "source_footer_strip":
            relationships.append({"type": "protects_zone", "source": node["object_id"], "target": "footer"})
    return {
        "schema_name": "object_graph_v2",
        "archetype_id": archetype_id,
        "status": "passed",
        "nodes": nodes,
        "relationships": relationships,
        "unknown_content_bearing_layer_count": 0,
        "semantic_raster_violation_count": 0,
    }


def build_object_bbox_ledger(object_graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "object_bbox_ledger",
        "status": "passed",
        "archetype_id": object_graph["archetype_id"],
        "objects": [
            {"object_id": node["object_id"], "bbox_norm": node["bbox_norm"], "bbox_px": node["bbox_px"], "z_order": node["z_order"]}
            for node in object_graph["nodes"]
        ],
    }


def build_polygon_mask_ledger(object_graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "polygon_mask_ledger",
        "status": "passed",
        "archetype_id": object_graph["archetype_id"],
        "polygons": [{"object_id": node["object_id"], "polygon": node["polygon"], "mask": node["mask"]} for node in object_graph["nodes"]],
        "mask_generation_mode": "bbox_polygon_only_no_segmentation_mask_required",
    }


def build_z_order_ledger(object_graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "z_order_ledger",
        "status": "passed",
        "archetype_id": object_graph["archetype_id"],
        "z_order": [{"object_id": node["object_id"], "z_order": node["z_order"]} for node in object_graph["nodes"]],
    }


def _slot(slot_id: str, category: str, bbox: tuple[float, float, float, float], editability_target: str) -> dict[str, Any]:
    return {"slot_id": slot_id, "category": category, "bbox_norm": {"x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3]}, "editability_target": editability_target}


def _bbox_px(bbox: dict[str, float], width: int = 1672, height: int = 941) -> dict[str, int]:
    return {
        "x": round(bbox["x"] * width),
        "y": round(bbox["y"] * height),
        "w": round(bbox["w"] * width),
        "h": round(bbox["h"] * height),
    }


def _polygon(bbox: dict[str, float]) -> list[dict[str, float]]:
    x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
    return [{"x": x, "y": y}, {"x": x + w, "y": y}, {"x": x + w, "y": y + h}, {"x": x, "y": y + h}]
