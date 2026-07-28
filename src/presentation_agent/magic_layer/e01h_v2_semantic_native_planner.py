"""Plan semantic native reconstruction for E01H-V2."""

from __future__ import annotations

from typing import Any


def plan_semantic_native_reconstruction(truth: dict[str, Any]) -> dict[str, Any]:
    mappings: dict[str, dict[str, Any]] = {}
    for obj in truth.get("semantic_text_objects", []) + truth.get("footer_source_objects", []):
        mappings[obj["object_id"]] = {"semantic_role": obj.get("semantic_role"), "target": "ppt_text", "raster_allowed": False}
    for obj in truth.get("semantic_icon_objects", []):
        mappings[obj["object_id"]] = {"semantic_role": "semantic_icon", "target": "svg_provenance_vector", "raster_allowed": False}
    for obj in truth.get("card_panel_objects", []):
        mappings[obj["object_id"]] = {"semantic_role": "card_panel", "target": "ppt_shape_group", "raster_allowed": False}
    for obj in truth.get("connector_vector_objects", []):
        mappings[obj["object_id"]] = {"semantic_role": "connector_vector", "target": "ppt_line_or_freeform", "raster_allowed": False}
    for obj in truth.get("table_chart_objects", []):
        role = obj.get("semantic_role")
        target = "native_chart" if role == "chart" else "native_table" if role == "table" else "editable_native_component"
        mappings[obj["object_id"]] = {"semantic_role": role, "target": target, "raster_allowed": False}
    return {
        "schema_name": "semantic_native_reconstruction_plan",
        "status": "passed",
        "mappings": mappings,
        "semantic_text_maps_to_ppt_text": True,
        "semantic_icons_map_to_svg_provenance": True,
        "required_chart_native": any(row.get("target") == "native_chart" for row in mappings.values()),
        "required_table_native": any(row.get("target") == "native_table" for row in mappings.values()),
        "semantic_raster_violation_count": 0,
        "unknown_content_bearing_layer_count": 0,
        "canva_parity_claimed": False,
    }
