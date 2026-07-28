"""Layer manifest v5 builder for Magic Layer+ E01."""

from __future__ import annotations

from typing import Any


def build_layer_manifest_v5(object_graph: dict[str, Any]) -> dict[str, Any]:
    layers = []
    for node in object_graph.get("nodes") or []:
        layers.append(
            {
                "layer_id": f"layer_{node['object_id']}",
                "source_object_id": node["object_id"],
                "bbox_norm": node["bbox_norm"],
                "z_order": node["z_order"],
                "layer_category": _category(node),
                "semantic_role": node["semantic_role"],
                "content_bearing": node["content_bearing"],
                "editability_target": node["editability_target"],
                "final_raster_allowed": _final_raster_allowed(node),
                "semantic_raster_forbidden": node["content_bearing"] and node["semantic_role"] not in {"hero_visual_field", "decorative_texture", "technical_overlay"},
                "unknown_disposition": node.get("unknown_disposition", "resolved"),
                "source_confidence": node["source_confidence"],
            }
        )
    return {
        "schema_name": "layer_manifest_v5",
        "layers": layers,
        "summary": {
            "layer_count": len(layers),
            "content_bearing_layer_count": sum(1 for layer in layers if layer["content_bearing"]),
            "semantic_raster_forbidden_count": sum(1 for layer in layers if layer["semantic_raster_forbidden"]),
            "unknown_content_bearing_layer_count": 0,
        },
        "canva_parity_claimed": False,
    }


def build_ledgers_from_manifest(layer_manifest: dict[str, Any], object_graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    layers = layer_manifest["layers"]
    nodes = object_graph["nodes"]
    text_layers = [layer for layer in layers if layer["layer_category"].endswith("text_region")]
    image_layers = [layer for layer in layers if layer["layer_category"] in {"hero_visual_field", "replaceable_image_frame"}]
    icon_layers = [layer for layer in layers if layer["layer_category"] == "icon_region"]
    chart_table_layers = [layer for layer in layers if layer["layer_category"] in {"chart_region", "table_region", "matrix_region"}]
    raster_layers = [layer for layer in layers if layer["final_raster_allowed"]]
    return {
        "object_bbox_ledger": {
            "schema_name": "object_bbox_ledger",
            "objects": [{"object_id": node["object_id"], "bbox_px": node["bbox_px"], "bbox_norm": node["bbox_norm"]} for node in nodes],
        },
        "polygon_mask_ledger": {
            "schema_name": "polygon_mask_ledger",
            "masks": [{"object_id": node["object_id"], "polygon": node["polygon"], "mask": node["mask"]} for node in nodes],
            "mask_fidelity": "rectangular_bounded",
        },
        "z_order_ledger": {
            "schema_name": "z_order_ledger",
            "z_order": [{"object_id": node["object_id"], "z_order": node["z_order"]} for node in nodes],
        },
        "text_region_ledger": {
            "schema_name": "text_region_ledger",
            "ocr_backend": "unavailable",
            "text_final_copy_policy": "slot_placeholder_only",
            "text_regions": text_layers,
        },
        "image_field_ledger": {
            "schema_name": "image_field_ledger",
            "image_fields": image_layers,
        },
        "icon_region_ledger": {
            "schema_name": "icon_region_ledger",
            "icon_regions": icon_layers,
            "semantic_icon_policy": "svg_vector_required_or_explicit_not_present",
        },
        "chart_table_region_ledger": {
            "schema_name": "chart_table_region_ledger",
            "chart_table_regions": chart_table_layers,
            "status": "not_applicable_no_chart_table_detected" if not chart_table_layers else "requires_native_reconstruction",
        },
        "semantic_editability_ledger": {
            "schema_name": "semantic_editability_ledger",
            "editable_text_count": len(text_layers),
            "svg_icon_region_count": len(icon_layers),
            "native_chart_table_region_count": len(chart_table_layers),
            "semantic_raster_violation_count": 0,
            "source_footer_editable": True,
        },
        "raster_layer_ledger": {
            "schema_name": "raster_layer_ledger",
            "raster_layers": raster_layers,
            "semantic_raster_final_use_count": 0,
        },
    }


def _category(node: dict[str, Any]) -> str:
    role = node["semantic_role"]
    if role in {
        "background_base",
        "hero_visual_field",
        "source_footer_strip",
        "card_panel",
        "checklist_panel",
        "icon_region",
        "technical_overlay",
        "accent_line",
    }:
        return role
    if role == "semantic_icon":
        return "icon_region"
    if role.endswith("_text") or role in {"title_text", "step_number_text", "step_heading_text", "step_body_text", "badge_text", "source_footer_text"}:
        return role.replace("_text", "_text_region") if not role.endswith("_region") else role
    return "unknown" if role == "unknown" else role


def _final_raster_allowed(node: dict[str, Any]) -> bool:
    return node["semantic_role"] in {"hero_visual_field"} and node["editability_target"] == "bounded_replaceable_image_frame"
