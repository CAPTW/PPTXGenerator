"""Crosswalk PS-layer records to rendered/PPTX inventory visibility."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e01x_duplicate_bbox_detector import detect_duplicate_bbox_collisions


def build_ps_layer_render_crosswalk(protocol: dict[str, Any], object_graph: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    nodes = object_graph.get("nodes", [])
    duplicate_report = detect_duplicate_bbox_collisions(nodes)
    hidden_by_object = {row["object_id"]: row for row in duplicate_report.get("visibility", []) if row.get("render_visibility") != "visible"}
    inventory_by_name = {shape.get("shape_name"): shape for shape in inventory.get("shapes", [])}
    node_by_id = {node.get("object_id"): node for node in nodes}
    rows = []
    errors: list[dict[str, Any]] = []
    for layer in protocol.get("layers", []):
        if not (layer.get("content_bearing") or layer.get("layer_kind") == "smart_object_like_image"):
            continue
        object_id = (layer.get("pptx_target") or {}).get("object_id")
        node = node_by_id.get(object_id)
        shape = inventory_by_name.get(object_id)
        if node is None:
            visibility = "missing_object_graph_node"
            errors.append({"code": visibility, "layer_id": layer.get("layer_id"), "object_id": object_id})
        elif object_id in hidden_by_object:
            visibility = "occluded_by_duplicate_bbox"
            errors.append({"code": visibility, "layer_id": layer.get("layer_id"), "object_id": object_id})
        elif shape is None:
            visibility = "missing_pptx_inventory_shape"
            errors.append({"code": visibility, "layer_id": layer.get("layer_id"), "object_id": object_id})
        else:
            visibility = "visible"
        if shape and shape.get("is_picture") and _is_semantic_layer(layer):
            errors.append({"code": "semantic_layer_rendered_as_picture", "layer_id": layer.get("layer_id"), "object_id": object_id})
        rows.append(
            {
                "layer_id": layer.get("layer_id"),
                "semantic_role": layer.get("semantic_role"),
                "object_id": object_id,
                "render_visibility": visibility,
                "bbox_norm": (node or {}).get("bbox_norm"),
                "pptx_shape_present": shape is not None,
            }
        )
    visible_counts = dict(duplicate_report.get("visible_counts") or {})
    required_failures = []
    for slot, required in {"card_panel": 3, "card_text": 3}.items():
        if int(visible_counts.get(slot, 0)) < required:
            required_failures.append({"code": f"{slot}_visible_count_lt_required", "visible_count": visible_counts.get(slot, 0), "required": required})
    errors.extend(required_failures)
    return {
        "schema_name": "ps_layer_render_crosswalk_report",
        "status": "passed" if not errors else "failed",
        "rows": rows,
        "visible_counts": visible_counts,
        "duplicate_collision_count": duplicate_report.get("collision_count", 0),
        "errors": errors,
        "error_count": len(errors),
        "canva_parity_claimed": False,
    }


def _is_semantic_layer(layer: dict[str, Any]) -> bool:
    role = str(layer.get("semantic_role") or "")
    return bool(layer.get("content_bearing")) and role not in {"hero_visual_field", "decorative_texture"}
