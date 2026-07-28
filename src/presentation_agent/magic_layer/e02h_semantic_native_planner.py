"""Semantic native reconstruction planning for E02H."""

from __future__ import annotations

from typing import Any


def build_e02h_semantic_native_plan(object_graph: dict[str, Any], reference_id: str) -> dict[str, dict[str, Any]]:
    semantic_classes = {"semantic_editable", "semantic_vector", "semantic_native_component"}
    actions = []
    semantic_raster = 0
    for node in object_graph.get("nodes", []):
        if node["layer_class"] not in semantic_classes:
            continue
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
    chart_count = sum(1 for row in actions if row["target_ppt_object_type"] in {"native_chart", "editable_shape_chart"})
    table_count = sum(1 for row in actions if row["target_ppt_object_type"] in {"native_table", "editable_shape_grid_table"})
    text_count = sum(1 for row in actions if row["target_ppt_object_type"] == "ppt_text_box")
    icon_count = sum(1 for row in actions if row["target_ppt_object_type"] == "native_vector")
    panel_count = sum(1 for row in actions if row["target_ppt_object_type"] in {"ppt_shape", "ppt_group"})
    plan = {
        "schema_name": "semantic_native_reconstruction_plan",
        "status": "passed" if semantic_raster == 0 and object_graph.get("unknown_content_bearing_layer_count", 0) == 0 else "failed",
        "reference_id": reference_id,
        "action_count": len(actions),
        "semantic_raster_mapping_count": semantic_raster,
        "unknown_content_bearing_layer_count": object_graph.get("unknown_content_bearing_layer_count", 0),
        "chart_table_status": _chart_table_status(reference_id, chart_count, table_count),
        "actions": actions,
        "canva_parity_claimed": False,
    }
    manifest = {
        "schema_name": "semantic_native_layer_manifest",
        "status": plan["status"],
        "reference_id": reference_id,
        "semantic_layer_count": len(actions),
        "editable_text_layer_count": text_count,
        "native_icon_layer_count": icon_count,
        "native_card_panel_layer_count": panel_count,
        "native_chart_count": chart_count,
        "native_table_count": table_count,
        "layers": actions,
        "canva_parity_claimed": False,
    }
    promotion = {
        "schema_name": "native_component_promotion_report",
        "status": plan["status"],
        "reference_id": reference_id,
        "promoted_text_count": text_count,
        "promoted_icon_count": icon_count,
        "promoted_card_panel_count": panel_count,
        "promoted_chart_count": chart_count,
        "promoted_table_count": table_count,
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
    if node["object_type"] == "connector":
        return "ppt_connector"
    if node["object_type"] == "chart":
        return "native_chart"
    if node["object_type"] == "table":
        return "native_table"
    if node["object_type"] in {"card", "panel"}:
        return "ppt_shape"
    return "ppt_shape"


def _chart_table_status(reference_id: str, chart_count: int, table_count: int) -> str:
    if reference_id == "data_dashboard_hybrid":
        return "passed_native_chart" if chart_count else "failed_missing_native_chart"
    if reference_id == "table_matrix_hybrid":
        return "passed_native_table" if table_count else "failed_missing_native_table"
    return "not_applicable_no_chart_table_required"
