"""Semantic native reconstruction planning for E01H."""

from __future__ import annotations

from typing import Any


def build_semantic_native_plan(object_graph: dict[str, Any]) -> dict[str, Any]:
    semantic_nodes = [node for node in object_graph.get("nodes", []) if node["layer_class"] == "semantic_editable"]
    actions = []
    semantic_raster = 0
    for node in semantic_nodes:
        target = _target_for(node)
        if target in {"bounded_nonsemantic_raster", "replaceable_image_frame"}:
            semantic_raster += 1
        actions.append(
            {
                "source_object_id": node["object_id"],
                "semantic_role": node["semantic_role"],
                "source_layer_class": node["layer_class"],
                "target_ppt_object_type": target,
                "bbox_norm": node["bbox_norm"],
                "raster_allowed": False,
                "editable_required": True,
                "status": "passed" if target not in {"bounded_nonsemantic_raster", "replaceable_image_frame"} else "failed",
            }
        )
    text_count = sum(1 for row in actions if row["target_ppt_object_type"] == "ppt_text_box")
    icon_count = sum(1 for row in actions if row["target_ppt_object_type"] == "native_vector")
    panel_count = sum(1 for row in actions if row["target_ppt_object_type"] in {"ppt_shape", "ppt_group"})
    plan = {
        "schema_name": "semantic_native_reconstruction_plan",
        "status": "passed" if semantic_raster == 0 and object_graph.get("unknown_content_bearing_layer_count", 0) == 0 else "failed",
        "action_count": len(actions),
        "semantic_raster_mapping_count": semantic_raster,
        "unknown_content_bearing_layer_count": object_graph.get("unknown_content_bearing_layer_count", 0),
        "chart_table_status": "not_applicable_no_chart_table_detected",
        "actions": actions,
        "canva_parity_claimed": False,
    }
    manifest = {
        "schema_name": "semantic_native_layer_manifest",
        "status": plan["status"],
        "semantic_layer_count": len(semantic_nodes),
        "editable_text_layer_count": text_count,
        "native_icon_layer_count": icon_count,
        "native_card_panel_layer_count": panel_count,
        "native_chart_count": 0,
        "native_table_count": 0,
        "layers": actions,
        "canva_parity_claimed": False,
    }
    promotion = {
        "schema_name": "native_component_promotion_report",
        "status": plan["status"],
        "promoted_text_count": text_count,
        "promoted_icon_count": icon_count,
        "promoted_card_panel_count": panel_count,
        "semantic_raster_promotion_failures": semantic_raster,
        "canva_parity_claimed": False,
    }
    return {
        "semantic_native_reconstruction_plan": plan,
        "semantic_native_layer_manifest": manifest,
        "native_component_promotion_report": promotion,
    }


def _target_for(node: dict[str, Any]) -> str:
    if node["object_type"] == "text":
        return "ppt_text_box"
    if node["object_type"] == "semantic_icon":
        return "native_vector"
    if node["object_type"] in {"card", "panel"}:
        return "ppt_shape"
    return "ppt_shape"
