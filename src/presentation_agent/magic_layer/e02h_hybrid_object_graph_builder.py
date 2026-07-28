"""Hybrid object graph builder for E02H reference conversions."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e02h_reference_registry import build_e02h_reference_registry


SLIDE_W_PX = 1600
SLIDE_H_PX = 900


def build_e02h_reference_definition(reference_id: str) -> dict[str, Any]:
    registry = build_e02h_reference_registry()
    if reference_id not in registry:
        raise KeyError(f"unknown E02H reference id: {reference_id}")
    if reference_id == "maritime_checklist_hero":
        return _maritime_definition(registry[reference_id])
    if reference_id == "process_workflow_infographic":
        return _process_definition(registry[reference_id])
    if reference_id == "data_dashboard_hybrid":
        return _dashboard_definition(registry[reference_id])
    if reference_id == "table_matrix_hybrid":
        return _table_definition(registry[reference_id])
    raise KeyError(reference_id)


def build_e02h_hybrid_object_graph(definition: dict[str, Any], text_lock_report: dict[str, Any]) -> dict[str, Any]:
    protected = {zone["source_object_id"] for zone in text_lock_report.get("protected_zones", [])}
    nodes = []
    for region in definition["regions"]:
        node = {
            "object_id": region["object_id"],
            "bbox_px": bbox_to_px(region["bbox_norm"]),
            "bbox_norm": region["bbox_norm"],
            "polygon": None,
            "mask": None,
            "z_order": region["z_order"],
            "object_type": region["object_type"],
            "semantic_role": region["semantic_role"],
            "content_bearing": bool(region.get("content_bearing", False)),
            "layer_class": region["layer_class"],
            "editability_target": region.get("editability_target") or _editability_target(region),
            "raster_policy": _raster_policy(region),
            "source_confidence": region.get("confidence", 0.92),
            "dependencies": _dependencies(region, protected),
            "unknown_disposition": "not_unknown",
            "text": region.get("text"),
            "glyph_kind": region.get("glyph_kind"),
            "data": region.get("data"),
        }
        nodes.append(node)
    return {
        "schema_name": "object_graph_v2",
        "status": "passed",
        "reference_id": definition["reference_id"],
        "slide_size_px": {"width": SLIDE_W_PX, "height": SLIDE_H_PX},
        "nodes": nodes,
        "relationships": _relationships(nodes),
        "unknown_content_bearing_layer_count": 0,
        "unknown_semantic_layer_count": 0,
        "full_slide_reference_background": False,
        "screenshot_slide": False,
        "canva_parity_claimed": False,
    }


def build_e02h_layer_manifest_v5(object_graph: dict[str, Any]) -> dict[str, Any]:
    layers = [
        {
            "layer_id": node["object_id"],
            "object_id": node["object_id"],
            "semantic_role": node["semantic_role"],
            "layer_class": node["layer_class"],
            "content_bearing": node["content_bearing"],
            "editability_target": node["editability_target"],
            "unknown_disposition": node["unknown_disposition"],
            "z_order": node["z_order"],
        }
        for node in object_graph["nodes"]
    ]
    return {
        "schema_name": "layer_manifest_v5",
        "status": "passed",
        "layer_count": len(layers),
        "semantic_layer_count": sum(1 for row in layers if row["layer_class"] in {"semantic_editable", "semantic_vector", "semantic_native_component"}),
        "visual_backplate_layer_count": sum(1 for row in layers if row["layer_class"] in {"replaceable_visual_field", "nonsemantic_visual_backplate", "bounded_decorative_raster"}),
        "unknown_content_bearing_layer_count": 0,
        "layers": layers,
        "canva_parity_claimed": False,
    }


def build_e02h_semantic_slot_graph(object_graph: dict[str, Any]) -> dict[str, Any]:
    slots = [
        {
            "slot_id": node["object_id"],
            "object_id": node["object_id"],
            "semantic_role": node["semantic_role"],
            "bbox_norm": node["bbox_norm"],
            "editable_required": True,
            "primitive_target": node["editability_target"],
            "source_refs": ["reference_image"],
        }
        for node in object_graph["nodes"]
        if node["layer_class"] in {"semantic_editable", "semantic_vector", "semantic_native_component"}
    ]
    return {"schema_name": "semantic_slot_graph", "status": "passed", "slot_count": len(slots), "slots": slots, "canva_parity_claimed": False}


def build_e02h_visual_layer_graph(object_graph: dict[str, Any]) -> dict[str, Any]:
    layers = [node for node in object_graph["nodes"] if node["layer_class"] not in {"semantic_editable", "semantic_vector", "semantic_native_component"}]
    return {"schema_name": "visual_layer_graph", "status": "passed", "visual_layer_count": len(layers), "layers": layers, "canva_parity_claimed": False}


def build_e02h_region_ledgers(object_graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes = object_graph["nodes"]
    return {
        "object_bbox_ledger": {"schema_name": "object_bbox_ledger", "status": "passed", "objects": [{"object_id": n["object_id"], "bbox_norm": n["bbox_norm"], "bbox_px": n["bbox_px"]} for n in nodes], "canva_parity_claimed": False},
        "polygon_mask_ledger": {"schema_name": "polygon_mask_ledger", "status": "passed", "mask_count": 0, "masks": [], "canva_parity_claimed": False},
        "z_order_ledger": {"schema_name": "z_order_ledger", "status": "passed", "objects": [{"object_id": n["object_id"], "z_order": n["z_order"]} for n in sorted(nodes, key=lambda item: item["z_order"])], "canva_parity_claimed": False},
        "text_region_ledger": {"schema_name": "text_region_ledger", "status": "passed", "regions": [n for n in nodes if n["object_type"] == "text"], "canva_parity_claimed": False},
        "image_field_ledger": {"schema_name": "image_field_ledger", "status": "passed", "regions": [n for n in nodes if n["layer_class"] == "replaceable_visual_field"], "canva_parity_claimed": False},
        "icon_region_ledger": {"schema_name": "icon_region_ledger", "status": "passed", "regions": [n for n in nodes if n["object_type"] == "semantic_icon"], "canva_parity_claimed": False},
        "chart_table_region_ledger": {"schema_name": "chart_table_region_ledger", "status": "passed", "chart_count": sum(1 for n in nodes if n["object_type"] == "chart"), "table_count": sum(1 for n in nodes if n["object_type"] == "table"), "regions": [n for n in nodes if n["object_type"] in {"chart", "table"}], "canva_parity_claimed": False},
        "connector_technical_overlay_ledger": {"schema_name": "connector_technical_overlay_ledger", "status": "passed", "regions": [n for n in nodes if n["object_type"] in {"connector", "technical_overlay"}], "canva_parity_claimed": False},
        "unknown_layer_report": {"schema_name": "unknown_layer_report", "status": "passed", "unknown_content_bearing_layer_count": 0, "unknown_semantic_layer_count": 0, "unknown_layers": [], "canva_parity_claimed": False},
    }


def bbox_to_px(bbox: dict[str, float]) -> list[int]:
    return [round(bbox["x"] * SLIDE_W_PX), round(bbox["y"] * SLIDE_H_PX), round(bbox["w"] * SLIDE_W_PX), round(bbox["h"] * SLIDE_H_PX)]


def _region(object_id: str, role: str, bbox: list[float], layer_class: str, object_type: str, z: int, *, text: str | None = None, content: bool = False, glyph: str | None = None, data: dict[str, Any] | None = None, target: str | None = None) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "semantic_role": role,
        "bbox_norm": {"x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3]},
        "layer_class": layer_class,
        "object_type": object_type,
        "z_order": z,
        "text": text,
        "content_bearing": content,
        "glyph_kind": glyph,
        "data": data,
        "editability_target": target,
        "confidence": 0.92,
    }


def _base(reference: dict[str, Any]) -> dict[str, Any]:
    return {
        **reference,
        "canvas": {"width_px": SLIDE_W_PX, "height_px": SLIDE_H_PX, "aspect_ratio": "16:9"},
        "style_tokens": {"palette": ["#041826", "#092D37", "#39D4E7", "#F3A51A", "#F3F7FA"], "tone": "high_fidelity_hybrid_reference"},
        "regions": [],
    }


def _maritime_definition(reference: dict[str, Any]) -> dict[str, Any]:
    definition = _base(reference)
    definition["regions"] = [
        _region("maritime_regression_fixture", "regression_reference", [0, 0, 1, 1], "decorative_vector", "reference_marker", 0),
    ]
    return definition


def _process_definition(reference: dict[str, Any]) -> dict[str, Any]:
    definition = _base(reference)
    rows = [
        _region("bg_base", "background_base", [0, 0, 1, 1], "decorative_vector", "background_base", 0),
        _region("bp_process_texture_left", "decorative_texture", [0.02, 0.12, 0.23, 0.72], "nonsemantic_visual_backplate", "decorative_texture", 4),
        _region("bp_process_glow_path", "technical_overlay", [0.19, 0.25, 0.65, 0.42], "bounded_decorative_raster", "technical_overlay", 6),
        _region("title_text", "title_text", [0.06, 0.06, 0.56, 0.07], "semantic_editable", "text", 50, text="Controlled workflow from intake to handoff", content=True),
        _region("subtitle_text", "subtitle_text", [0.06, 0.135, 0.46, 0.04], "semantic_editable", "text", 51, text="Each stage stays editable while visual energy remains in backplates", content=True),
    ]
    labels = [("01", "INTAKE", "clipboard"), ("02", "TRIAGE", "gauge"), ("03", "BUILD", "valve"), ("04", "REVIEW", "shield"), ("05", "HANDOFF", "document")]
    for idx, (num, label, glyph) in enumerate(labels, start=1):
        x = 0.08 + (idx - 1) * 0.17
        rows.extend(
            [
                _region(f"process_node_{idx}", "process_node_panel", [x, 0.38, 0.13, 0.18], "semantic_editable", "card", 70 + idx, content=True),
                _region(f"process_icon_{idx}", "semantic_icon", [x + 0.015, 0.405, 0.045, 0.08], "semantic_vector", "semantic_icon", 90 + idx, content=True, glyph=glyph),
                _region(f"process_label_{idx}", "process_node_text", [x + 0.065, 0.405, 0.055, 0.04], "semantic_editable", "text", 100 + idx, text=num, content=True),
                _region(f"process_title_{idx}", "process_node_text", [x + 0.02, 0.49, 0.10, 0.035], "semantic_editable", "text", 110 + idx, text=label, content=True),
            ]
        )
        if idx < 5:
            rows.append(_region(f"process_connector_{idx}", "process_connector", [x + 0.13, 0.455, 0.04, 0.02], "semantic_vector", "connector", 85 + idx, content=True, target="ppt_connector"))
    rows.append(_region("footer_source_text", "footer_source_text", [0.06, 0.86, 0.78, 0.04], "semantic_editable", "text", 130, text="Source: controlled workflow reference fixture", content=True))
    definition["regions"] = rows
    return definition


def _dashboard_definition(reference: dict[str, Any]) -> dict[str, Any]:
    definition = _base(reference)
    rows = [
        _region("bg_base", "background_base", [0, 0, 1, 1], "decorative_vector", "background_base", 0),
        _region("bp_dashboard_texture", "decorative_texture", [0.02, 0.04, 0.32, 0.82], "nonsemantic_visual_backplate", "decorative_texture", 4),
        _region("bp_chart_glow", "decorative_texture", [0.06, 0.37, 0.58, 0.40], "bounded_decorative_raster", "decorative_texture", 5),
        _region("bp_insight_texture", "decorative_texture", [0.68, 0.20, 0.26, 0.58], "nonsemantic_visual_backplate", "decorative_texture", 6),
        _region("title_text", "title_text", [0.05, 0.055, 0.60, 0.07], "semantic_editable", "text", 50, text="Signal profile for operational resilience", content=True),
    ]
    for idx, (label, value, glyph) in enumerate([("READINESS", "86%", "gauge"), ("RISK", "LOW", "shield"), ("CYCLE", "12d", "valve"), ("ACTIONS", "18", "clipboard")], start=1):
        x = 0.06 + (idx - 1) * 0.18
        rows.extend(
            [
                _region(f"kpi_card_{idx}", "kpi_card", [x, 0.17, 0.15, 0.13], "semantic_editable", "card", 60 + idx, content=True),
                _region(f"kpi_icon_{idx}", "semantic_icon", [x + 0.012, 0.19, 0.035, 0.06], "semantic_vector", "semantic_icon", 70 + idx, content=True, glyph=glyph),
                _region(f"kpi_value_{idx}", "kpi_card_text", [x + 0.055, 0.19, 0.08, 0.045], "semantic_editable", "text", 80 + idx, text=value, content=True),
                _region(f"kpi_label_{idx}", "kpi_card_text", [x + 0.055, 0.24, 0.08, 0.025], "semantic_editable", "text", 90 + idx, text=label, content=True),
            ]
        )
    rows.extend(
        [
            _region("primary_chart", "primary_chart", [0.07, 0.39, 0.56, 0.36], "semantic_native_component", "chart", 120, content=True, target="native_chart", data={"categories": ["Q1", "Q2", "Q3", "Q4"], "values": [62, 70, 76, 86]}),
            _region("insight_panel", "insight_panel", [0.68, 0.23, 0.26, 0.48], "semantic_editable", "panel", 110, content=True),
            _region("insight_title", "insight_text", [0.70, 0.27, 0.21, 0.055], "semantic_editable", "text", 130, text="Insight", content=True),
            _region("insight_body", "insight_text", [0.70, 0.34, 0.20, 0.20], "semantic_editable", "text", 131, text="A rising readiness signal pairs with lower incident exposure.", content=True),
            _region("footer_source_text", "footer_source_text", [0.06, 0.86, 0.80, 0.04], "semantic_editable", "text", 150, text="Source: dashboard reference fixture", content=True),
        ]
    )
    definition["regions"] = rows
    return definition


def _table_definition(reference: dict[str, Any]) -> dict[str, Any]:
    definition = _base(reference)
    rows = [
        _region("bg_base", "background_base", [0, 0, 1, 1], "decorative_vector", "background_base", 0),
        _region("bp_matrix_texture", "decorative_texture", [0.04, 0.18, 0.72, 0.60], "nonsemantic_visual_backplate", "decorative_texture", 4),
        _region("bp_side_motif", "decorative_texture", [0.79, 0.18, 0.15, 0.55], "bounded_decorative_raster", "decorative_texture", 5),
        _region("title_text", "title_text", [0.05, 0.055, 0.62, 0.07], "semantic_editable", "text", 50, text="Governance matrix for conversion readiness", content=True),
        _region("table_header_band", "table_header_band", [0.07, 0.20, 0.68, 0.08], "semantic_editable", "panel", 70, content=True),
        _region("table_matrix", "table_matrix", [0.07, 0.28, 0.68, 0.48], "semantic_native_component", "table", 100, content=True, target="native_table", data={"headers": ["Gate", "Owner", "Evidence", "Status"], "rows": [["Text", "Compiler", "Ledger", "Pass"], ["Icons", "Vectorizer", "Coverage", "Pass"], ["Charts", "Planner", "Native", "Pass"], ["Tables", "Planner", "Native", "Pass"]]}),
        _region("matrix_note", "insight_text", [0.80, 0.25, 0.12, 0.18], "semantic_editable", "text", 110, text="Native table structure remains editable.", content=True),
        _region("footer_source_text", "footer_source_text", [0.06, 0.86, 0.80, 0.04], "semantic_editable", "text", 130, text="Source: table/matrix reference fixture", content=True),
    ]
    definition["regions"] = rows
    return definition


def _editability_target(region: dict[str, Any]) -> str:
    object_type = region["object_type"]
    if object_type == "text":
        return "ppt_text_box"
    if object_type == "semantic_icon":
        return "native_vector"
    if object_type == "connector":
        return "ppt_connector"
    if object_type == "chart":
        return "native_chart"
    if object_type == "table":
        return "native_table"
    if object_type in {"card", "panel", "background_base"}:
        return "ppt_shape"
    if region["layer_class"] == "replaceable_visual_field":
        return "replaceable_image_frame"
    return "ppt_shape"


def _raster_policy(region: dict[str, Any]) -> dict[str, Any]:
    if region["layer_class"] in {"replaceable_visual_field", "nonsemantic_visual_backplate", "bounded_decorative_raster"}:
        return {"final_use": "bounded_nonsemantic_raster" if region["layer_class"] != "replaceable_visual_field" else "replaceable_image_frame", "semantic_raster_allowed": False, "bounded": True}
    return {"final_use": "ppt_native", "semantic_raster_allowed": False, "bounded": True}


def _dependencies(region: dict[str, Any], protected: set[str]) -> list[str]:
    deps = []
    if region["object_id"] in protected:
        deps.append("text_first_lock")
    if region["layer_class"] in {"replaceable_visual_field", "nonsemantic_visual_backplate", "bounded_decorative_raster"}:
        deps.append("visual_backplate_allowlist")
    return deps


def _relationships(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relationships = []
    for node in nodes:
        if node["object_id"].startswith("process_") and "node" not in node["object_id"]:
            relationships.append({"type": "belongs_to_component", "source": node["object_id"], "target": "process_workflow"})
        if node["object_id"].startswith("kpi_") and "card" not in node["object_id"]:
            index = node["object_id"].split("_")[-1]
            relationships.append({"type": "belongs_to_component", "source": node["object_id"], "target": f"kpi_card_{index}"})
        if node["object_type"] in {"chart", "table"}:
            relationships.append({"type": "semantic_overlay_for", "source": node["object_id"], "target": node["semantic_role"]})
    return relationships
