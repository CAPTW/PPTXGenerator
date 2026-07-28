"""Plan and apply the E01X-P visual slot geometry patch."""

from __future__ import annotations

import copy
from typing import Any


CARD_PANEL_TARGETS = {
    "card_panel_1": {"x": 0.07, "y": 0.36, "w": 0.16, "h": 0.25},
    "card_panel_2": {"x": 0.255, "y": 0.36, "w": 0.16, "h": 0.25},
    "card_panel_3": {"x": 0.44, "y": 0.36, "w": 0.16, "h": 0.25},
}
CARD_TEXT_TARGETS = {
    "card_text_1": {"x": 0.085, "y": 0.40, "w": 0.13, "h": 0.14},
    "card_text_2": {"x": 0.27, "y": 0.40, "w": 0.13, "h": 0.14},
    "card_text_3": {"x": 0.455, "y": 0.40, "w": 0.13, "h": 0.14},
}
SEMANTIC_ICON_TARGET = {"x": 0.083, "y": 0.645, "w": 0.047, "h": 0.085}
TECHNICAL_OVERLAY_TARGET = {"x": 0.05, "y": 0.78, "w": 0.68, "h": 0.06}


def plan_geometry_patch(object_graph: dict[str, Any], duplicate_report: dict[str, Any]) -> dict[str, Any]:
    object_ids = {node["object_id"] for node in object_graph.get("nodes", [])}
    operations: list[dict[str, Any]] = []
    for object_id, bbox in {**CARD_PANEL_TARGETS, **CARD_TEXT_TARGETS}.items():
        if object_id in object_ids:
            operations.append({"operation": "update_bbox", "object_id": object_id, "bbox_norm": bbox, "reason": "restore_three_card_slot_geometry"})
    if "semantic_icon" in object_ids:
        operations.append(
            {
                "operation": "update_bbox",
                "object_id": "semantic_icon",
                "bbox_norm": SEMANTIC_ICON_TARGET,
                "vector_motif": "cyan_circle_with_inner_triangle",
                "reason": "restore_reference_icon_motif",
            }
        )
    if "technical_overlay" in object_ids:
        operations.append(
            {
                "operation": "update_bbox",
                "object_id": "technical_overlay",
                "bbox_norm": TECHNICAL_OVERLAY_TARGET,
                "vector_motif": "connector_dot_line",
                "reason": "strengthen_lower_technical_connector_motif",
            }
        )
    for index, text_id in enumerate(("card_text_1", "card_text_2", "card_text_3"), start=1):
        if text_id in object_ids:
            operations.append({"operation": "ensure_shape", "object_id": f"card_underline_{index}", "source_object_id": text_id, "semantic_role": "card_underline", "reason": "restore_card_gold_underline"})
    return {
        "schema_name": "geometry_patch_plan",
        "status": "ready" if operations else "not_applicable",
        "input_duplicate_collision_count": duplicate_report.get("collision_count", 0),
        "operations": operations,
        "rules": [
            "spread_three_card_panels_horizontally",
            "place_each_card_text_inside_its_corresponding_card",
            "restore_gold_card_underlines_as_ppt_shapes",
            "restore_cyan_circle_triangle_icon_as_native_vector_shapes",
            "restore_lower_connector_dot_motif_as_ppt_shapes",
        ],
        "canva_parity_claimed": False,
    }


def apply_geometry_patch_to_object_graph(object_graph: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    patched = copy.deepcopy(object_graph)
    nodes = patched.setdefault("nodes", [])
    by_id = {node["object_id"]: node for node in nodes}
    for operation in plan.get("operations", []):
        if operation["operation"] == "update_bbox" and operation["object_id"] in by_id:
            node = by_id[operation["object_id"]]
            node["bbox_norm"] = dict(operation["bbox_norm"])
            node["bbox_px"] = _bbox_px(node["bbox_norm"])
            node["polygon"] = _polygon(node["bbox_norm"])
            if operation.get("vector_motif"):
                node["vector_motif"] = operation["vector_motif"]
        elif operation["operation"] == "ensure_shape":
            source = by_id.get(operation["source_object_id"])
            if source and operation["object_id"] not in by_id:
                underline = _underline_node(operation["object_id"], source)
                nodes.append(underline)
                by_id[underline["object_id"]] = underline
    nodes.sort(key=lambda node: (node.get("z_order", 0), node.get("object_id", "")))
    summary = dict(patched.get("summary") or {})
    summary["node_count"] = len(nodes)
    patched["summary"] = summary
    patched["geometry_patch_applied"] = True
    return patched


def build_patched_editable_candidate_spec(original_spec: dict[str, Any], patched_object_graph: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    spec = copy.deepcopy(original_spec)
    spec["schema_name"] = "patched_editable_candidate_spec"
    spec["geometry_patch"] = {"status": plan["status"], "operation_count": len(plan.get("operations", [])), "rules": plan.get("rules", [])}
    spec["objects"] = [
        {
            "object_id": node["object_id"],
            "semantic_role": node.get("semantic_role"),
            "bbox_norm": node.get("bbox_norm"),
            "editability_target": node.get("editability_target"),
            "object_type": node.get("object_type"),
            "z_order": node.get("z_order"),
        }
        for node in patched_object_graph.get("nodes", [])
    ]
    spec["object_count"] = len(spec["objects"])
    spec["full_slide_reference_background"] = False
    spec["screenshot_slide"] = False
    spec["semantic_raster_final_use_count"] = 0
    spec["canva_parity_claimed"] = False
    return spec


def _underline_node(object_id: str, source: dict[str, Any]) -> dict[str, Any]:
    bbox = source["bbox_norm"]
    underline = {"x": round(bbox["x"], 6), "y": round(bbox["y"] + 0.045, 6), "w": round(bbox["w"] * 0.76, 6), "h": 0.006}
    return {
        "object_id": object_id,
        "object_type": "shape",
        "semantic_role": "card_underline",
        "content_bearing": False,
        "bbox_norm": underline,
        "bbox_px": _bbox_px(underline),
        "polygon": _polygon(underline),
        "z_order": max(0, int(source.get("z_order", 34)) - 1),
        "editability_target": "ppt_shape",
        "unknown_disposition": "resolved",
        "source_confidence": source.get("source_confidence", 0.9),
    }


def _bbox_px(bbox: dict[str, float]) -> list[int]:
    return [round(bbox["x"] * 1672), round(bbox["y"] * 941), round(bbox["w"] * 1672), round(bbox["h"] * 941)]


def _polygon(bbox: dict[str, float]) -> list[list[float]]:
    x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
    return [[x, y], [round(x + w, 6), y], [round(x + w, 6), round(y + h, 6)], [x, round(y + h, 6)]]
