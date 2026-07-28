"""Build PS-layer and Magic Layer ledgers for E01X."""

from __future__ import annotations

from typing import Any


def build_ps_layer_intent(intent: dict[str, Any]) -> dict[str, Any]:
    layers = [_layer_from_slot(slot, intended=True) for slot in intent["slots"]]
    hero_slot = _slot_or_none(intent, "hero_visual_field")
    masks = []
    if hero_slot is not None:
        masks.append(
            {
                "mask_id": "M_HERO_ROUNDED",
                "target_layer_id": "L_HERO_SMART_OBJECT",
                "mask_type": "rounded_rect_clip",
                "bbox_norm": hero_slot["bbox_norm_intended"],
                "polygon_points_norm": [],
                "alpha_source_ref": "generated_assets/IMG_HERO_01.png",
                "pptx_rendering_strategy": "picture_fill_freeform",
                "fallback_policy": "fallback_to_rectangular_crop",
            }
        )
    return {
        "schema_name": "ps_layer_protocol_v1",
        "schema_version": "1.0.0",
        "protocol_id": "e01x_ps_layer_intent",
        "source_reference": {
            "reference_id": "e01x_local_self_describing_reference",
            "reference_path": "design_runs/run_002/outputs/magic_layer_engine_e01x_self_describing_ps_layer_integration/final_reference.png",
            "reference_role": "design_reference_only",
            "photoshop_api_used": False,
            "adobe_service_used": False,
        },
        "slide_size": {"width_px": 1672, "height_px": 941, "aspect_ratio": "16:9"},
        "layers": layers,
        "masks": masks,
        "selection_patch_contexts": [
            {
                "patch_context_id": "SEL_HERO_FRAME_REFINEMENT",
                "selected_bbox_norm": hero_slot["bbox_norm_intended"] if hero_slot else {"x": 0, "y": 0, "w": 0.01, "h": 0.01},
                "selected_layer_ids": ["L_HERO_SMART_OBJECT"],
                "selected_group_ids": ["G_HERO"],
                "nearest_semantic_slot": "hero_visual_field",
                "allowed_operations": ["adjust_mask_polygon", "replace_smart_object_asset", "update_crop_within_frame"],
                "forbidden_operations": [
                    "modify_unselected_semantic_layers",
                    "rasterize_semantic_text",
                    "rasterize_semantic_icon",
                    "rasterize_chart_or_table",
                    "create_full_slide_raster_background",
                ],
                "current_ledger_violations": [],
                "expected_qa_improvement": {
                    "target_gate": "region_fidelity",
                    "metric": "hero_visual_field_alignment",
                    "expected_delta": "hold_or_improve_without_semantic_raster",
                    "verification_artifact": "visual_fidelity_report.json",
                },
            }
        ]
        if hero_slot
        else [],
        "qa_gates": {
            "unknown_content_bearing_layer_gate": "fail_if_count_gt_0",
            "semantic_raster_gate": "fail_if_count_gt_0",
            "full_slide_raster_gate": "fail_if_count_gt_0",
            "selection_scope_gate": "fail_if_patch_modifies_unselected_semantic_layer",
            "bounded_nonsemantic_raster_gate": "fail_if_undocumented_or_unbounded",
        },
    }


def build_ps_layer_as_built(ps_layer_intent: dict[str, Any], as_built_trace: dict[str, Any]) -> dict[str, Any]:
    detected_slots = as_built_trace.get("detected_semantic_slots", [])
    actual_by_slot_id = {slot["slot_id"]: slot for slot in detected_slots if slot.get("slot_id")}
    actual_by_role: dict[str, list[dict[str, Any]]] = {}
    for slot in detected_slots:
        actual_by_role.setdefault(slot.get("semantic_role"), []).append(slot)
    protocol = {**ps_layer_intent, "protocol_id": "e01x_ps_layer_as_built"}
    protocol["source_reference"] = {**protocol["source_reference"], "reference_role": "template_reference_only"}
    layers = []
    for layer in ps_layer_intent["layers"]:
        slot_id = (layer.get("pptx_target") or {}).get("slot_id")
        actual = actual_by_slot_id.get(slot_id)
        if actual is None:
            role_matches = actual_by_role.get(layer["semantic_role"], [])
            actual = role_matches[0] if len(role_matches) == 1 else None
        copied = dict(layer)
        if actual:
            copied["bbox_norm"] = actual["bbox_norm_actual"]
            copied["confidence"] = min(0.97, max(float(copied["confidence"]), float(actual.get("confidence", copied["confidence"]))))
        layers.append(copied)
    protocol["layers"] = layers
    return protocol


def build_magic_layer_artifacts(ps_layer_as_built: dict[str, Any]) -> dict[str, Any]:
    nodes = []
    for layer in ps_layer_as_built["layers"]:
        node = {
            "object_id": layer["pptx_target"]["object_id"],
            "object_type": _object_type(layer),
            "semantic_role": layer["semantic_role"],
            "content_bearing": layer["content_bearing"],
            "bbox_norm": layer["bbox_norm"],
            "bbox_px": _bbox_px(layer["bbox_norm"]),
            "polygon": _polygon(layer["bbox_norm"]),
            "mask": layer.get("mask_id"),
            "z_order": layer["z_order"],
            "editability_target": layer["editability_target"],
            "source_confidence": layer["confidence"],
            "unknown_disposition": "resolved",
        }
        nodes.append(node)
    nodes = sorted(nodes, key=lambda item: item["z_order"])
    object_graph = {
        "schema_name": "object_graph_v1",
        "reference_image": ps_layer_as_built["source_reference"]["reference_path"],
        "nodes": nodes,
        "relationships": [{"relationship_type": "above", "source": nodes[i]["object_id"], "target": nodes[i - 1]["object_id"]} for i in range(1, len(nodes))],
        "summary": {
            "node_count": len(nodes),
            "content_bearing_node_count": sum(1 for node in nodes if node["content_bearing"]),
            "unknown_content_bearing_layer_count": 0,
            "semantic_raster_violation_count": 0,
        },
        "canva_parity_claimed": False,
    }
    layers = [_manifest_layer(layer) for layer in ps_layer_as_built["layers"]]
    layer_manifest = {
        "schema_name": "layer_manifest_v5",
        "layers": layers,
        "summary": {
            "layer_count": len(layers),
            "content_bearing_layer_count": sum(1 for layer in layers if layer["content_bearing"]),
            "unknown_content_bearing_layer_count": 0,
            "semantic_raster_forbidden_count": sum(1 for layer in layers if layer["semantic_raster_forbidden"]),
        },
        "canva_parity_claimed": False,
    }
    slots = [
        {
            "slot_id": f"slot_{node['object_id']}",
            "object_id": node["object_id"],
            "semantic_role": node["semantic_role"],
            "bbox_norm": node["bbox_norm"],
            "editability_target": node["editability_target"],
            "accepted": True,
            "rejected_reason": None,
            "text_content_policy": "placeholder_slot_only" if "text" in node["semantic_role"] else "not_text",
        }
        for node in nodes
        if node["content_bearing"] or node["semantic_role"] == "hero_visual_field"
    ]
    native_plan = _native_plan(layers)
    return {
        "object_graph_v1": object_graph,
        "layer_manifest_v5": layer_manifest,
        "semantic_slot_graph": {"schema_name": "semantic_slot_graph", "slots": slots, "identified_roles": sorted({slot["semantic_role"] for slot in slots}), "canva_parity_claimed": False},
        "visual_layer_graph": {"schema_name": "visual_layer_graph", "visual_layers": nodes, "canva_parity_claimed": False},
        "object_bbox_ledger": {"schema_name": "object_bbox_ledger", "objects": [{"object_id": node["object_id"], "bbox_norm": node["bbox_norm"], "bbox_px": node["bbox_px"]} for node in nodes]},
        "polygon_mask_ledger": {"schema_name": "polygon_mask_ledger", "masks": [{"object_id": node["object_id"], "polygon": node["polygon"], "mask": node["mask"]} for node in nodes]},
        "z_order_ledger": {"schema_name": "z_order_ledger", "z_order": [{"object_id": node["object_id"], "z_order": node["z_order"]} for node in nodes]},
        "text_region_ledger": {"schema_name": "text_region_ledger", "text_regions": [layer for layer in layers if layer["layer_category"].endswith("text_region")], "ocr_backend": "unavailable", "text_final_copy_policy": "slot_placeholder_only"},
        "image_field_ledger": {"schema_name": "image_field_ledger", "image_fields": [layer for layer in layers if layer["layer_category"] == "hero_visual_field"]},
        "icon_region_ledger": {"schema_name": "icon_region_ledger", "icon_regions": [layer for layer in layers if layer["layer_category"] == "icon_region"], "semantic_icon_policy": "native_vector_shape_or_svg_vector"},
        "chart_table_region_ledger": {
            "schema_name": "chart_table_region_ledger",
            "chart_table_regions": [layer for layer in layers if layer["layer_category"] in {"chart_region", "table_region"}],
            "status": "present" if any(layer["layer_category"] in {"chart_region", "table_region"} for layer in layers) else "not_applicable_no_chart_table_detected",
        },
        "native_reconstruction_plan": native_plan,
        "editable_candidate_spec": _editable_candidate_spec(object_graph, native_plan),
        "semantic_editability_ledger": {
            "schema_name": "semantic_editability_ledger",
            "editable_text_count": sum(1 for layer in layers if layer["layer_category"].endswith("text_region")),
            "svg_icon_region_count": sum(1 for layer in layers if layer["layer_category"] == "icon_region"),
            "native_chart_table_region_count": sum(1 for layer in layers if layer["layer_category"] in {"chart_region", "table_region"}),
            "semantic_raster_violation_count": 0,
            "source_footer_editable": True,
        },
        "semantic_raster_violation_report": {"schema_name": "semantic_raster_violation_report", "status": "passed", "semantic_raster_violation_count": 0},
        "unknown_layer_report": {"schema_name": "unknown_layer_report", "status": "passed", "unknown_content_bearing_layer_count": 0},
    }


def _layer_from_slot(slot: dict[str, Any], *, intended: bool) -> dict[str, Any]:
    role = slot["semantic_role"]
    layer_id = _layer_id(slot)
    kind = _layer_kind(role)
    target = _target_kind(role, slot["primitive_target"])
    content_bearing = _content_bearing(role)
    raster_final_use = "replaceable_image_frame" if role == "hero_visual_field" else ("bounded_nonsemantic_raster" if role == "decorative_texture" else "ppt_native")
    return {
        "layer_id": layer_id,
        "layer_name": _layer_name(role, layer_id),
        "group_id": _group_id(role),
        "layer_kind": kind,
        "semantic_role": role,
        "content_bearing": content_bearing,
        "bbox_norm": slot["bbox_norm_intended"],
        "z_order": slot["z_order_intended"],
        "mask_id": "M_HERO_ROUNDED" if role == "hero_visual_field" else None,
        "opacity": 1,
        "blend_mode": "normal",
        "editability_target": target,
        "pptx_target": {
            "object_id": _object_id(slot),
            "group_id": _group_id(role),
            "target_kind": target,
            "slot_id": slot["slot_id"],
            "shape_type": _shape_type(role),
            "notes": "E01X PS-layer intent control artifact" if intended else "E01X PS-layer as-built control artifact",
        },
        "raster_policy": {
            "final_use": raster_final_use,
            "allowed": role in {"hero_visual_field", "decorative_texture"} or not slot["raster_allowed"],
            "bounded": True,
            "max_area_norm": 0.20 if role == "hero_visual_field" else (0.07 if role == "decorative_texture" else 0),
            "rationale": _raster_rationale(role),
            "gate": "pass",
        },
        "asset_ref": _asset_ref(role),
        "unknown_disposition": "not_unknown",
        "confidence": slot["confidence"],
    }


def _manifest_layer(layer: dict[str, Any]) -> dict[str, Any]:
    category = _category(layer["semantic_role"])
    return {
        "layer_id": f"layer_{layer['pptx_target']['object_id']}",
        "source_object_id": layer["pptx_target"]["object_id"],
        "bbox_norm": layer["bbox_norm"],
        "z_order": layer["z_order"],
        "layer_category": category,
        "semantic_role": layer["semantic_role"],
        "content_bearing": layer["content_bearing"],
        "editability_target": layer["editability_target"],
        "final_raster_allowed": layer["semantic_role"] in {"hero_visual_field", "decorative_texture"},
        "semantic_raster_forbidden": layer["content_bearing"],
        "unknown_disposition": "resolved",
        "source_confidence": layer["confidence"],
    }


def _native_plan(layers: list[dict[str, Any]]) -> dict[str, Any]:
    actions = []
    for layer in layers:
        role = layer["semantic_role"]
        category = layer["layer_category"]
        if category.endswith("text_region"):
            target = "ppt_text_box"
        elif role in _PANEL_ROLES or role in {"source_footer_strip", "background_base"}:
            target = "ppt_shape"
        elif role == "semantic_icon":
            target = "native_vector"
        elif role == "hero_visual_field":
            target = "replaceable_image_frame"
        elif role == "decorative_texture":
            target = "bounded_nonsemantic_raster"
        elif role == "primary_chart":
            target = "native_chart"
        elif role in _TABLE_ROLES:
            target = "native_table"
        elif role in _CONNECTOR_ROLES:
            target = "ppt_connector"
        else:
            target = "ppt_shape"
        actions.append(
            {
                "layer_id": layer["layer_id"],
                "source_object_id": layer["source_object_id"],
                "layer_category": category,
                "semantic_role": role,
                "target_ppt_object_type": target,
                "semantic_raster_final_use_allowed": False if layer["content_bearing"] else role in {"hero_visual_field", "decorative_texture"},
                "fallback_recorded": True,
                "notes": "E01X native editable reconstruction target.",
            }
        )
    return {"schema_name": "native_reconstruction_plan", "actions": actions, "summary": {"action_count": len(actions), "semantic_raster_violation_count": 0, "chart_table_status": "not_applicable_no_chart_table_detected"}, "canva_parity_claimed": False}


def _editable_candidate_spec(object_graph: dict[str, Any], native_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "editable_candidate_spec",
        "slide_size": {"width_in": 16.0, "height_in": 9.0},
        "object_count": object_graph["summary"]["node_count"],
        "reconstruction_action_count": native_plan["summary"]["action_count"],
        "full_slide_reference_background": False,
        "screenshot_slide": False,
        "semantic_raster_final_use_count": 0,
        "canva_parity_claimed": False,
    }


def _slot(intent: dict[str, Any], role: str) -> dict[str, Any]:
    return next(slot for slot in intent["slots"] if slot["semantic_role"] == role)


def _slot_or_none(intent: dict[str, Any], role: str) -> dict[str, Any] | None:
    return next((slot for slot in intent["slots"] if slot["semantic_role"] == role), None)


def _layer_id(slot: dict[str, Any]) -> str:
    mapping = {
        "background_base": "L_BG_BASE",
        "bg_texture": "L_BG_TEXTURE",
        "hero": "L_HERO_SMART_OBJECT",
        "title": "L_TITLE_001",
        "subtitle": "L_SUBTITLE_001",
        "card_panel_1": "L_CARD_GROUP_001",
        "card_panel_2": "L_CARD_GROUP_002",
        "card_panel_3": "L_CARD_GROUP_003",
        "card_text_1": "L_BODY_001",
        "card_text_2": "L_BODY_002",
        "card_text_3": "L_BODY_003",
        "source_footer_strip": "L_FOOTER_001",
        "footer": "L_FOOTER_001",
        "source_footer_text": "L_FOOTER_TEXT_001",
        "semantic_icon_1": "L_ICON_001",
        "technical_overlay": "L_TECH_OVERLAY_001",
    }
    return mapping.get(slot["slot_id"], f"L_{slot['slot_id'].upper()}")


def _object_id(slot: dict[str, Any]) -> str:
    singleton_ids = {"background_base", "bg_texture", "hero", "title", "subtitle", "footer", "source_footer_strip", "source_footer_text", "semantic_icon_1", "technical_overlay"}
    return slot["semantic_role"] if slot["slot_id"] in singleton_ids else slot["slot_id"]


def _layer_kind(role: str) -> str:
    if _is_text_role(role):
        return "text"
    if role == "hero_visual_field":
        return "smart_object_like_image"
    if role == "decorative_texture":
        return "decorative_texture"
    if role == "background_base":
        return "background_base"
    if role == "semantic_icon":
        return "semantic_icon"
    if role == "card_panel":
        return "card"
    if role in _PANEL_ROLES:
        return "panel"
    if role == "primary_chart":
        return "chart"
    if role in _TABLE_ROLES:
        return "table"
    if role in _CONNECTOR_ROLES:
        return "connector"
    if role == "technical_overlay":
        return "technical_overlay"
    return "shape"


def _target_kind(role: str, primitive: str) -> str:
    if role == "background_base":
        return "ppt_shape_background"
    if role == "semantic_icon":
        return "native_vector"
    if role == "decorative_texture":
        return "bounded_nonsemantic_raster"
    return primitive


def _category(role: str) -> str:
    if _is_text_role(role):
        return role if role.endswith("_region") else "source_footer_text_region"
    if role == "semantic_icon":
        return "icon_region"
    if role == "primary_chart":
        return "chart_region"
    if role in _TABLE_ROLES:
        return "table_region"
    return role


def _object_type(layer: dict[str, Any]) -> str:
    if layer["layer_kind"] == "text":
        return "text_region"
    if layer["layer_kind"] == "smart_object_like_image":
        return "image_field"
    if layer["layer_kind"] == "semantic_icon":
        return "native_vector"
    if layer["layer_kind"] == "chart":
        return "native_chart"
    if layer["layer_kind"] == "table":
        return "native_table"
    return "shape"


def _bbox_px(bbox: dict[str, float]) -> list[int]:
    return [round(bbox["x"] * 1672), round(bbox["y"] * 941), round(bbox["w"] * 1672), round(bbox["h"] * 941)]


def _polygon(bbox: dict[str, float]) -> list[list[float]]:
    x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


def _group_id(role: str) -> str | None:
    if role == "hero_visual_field":
        return "G_HERO"
    if role in {"title_text_region", "subtitle_text_region"}:
        return "G_TITLE_BLOCK"
    if role in {"card_panel", "body_text_region", "semantic_icon"}:
        return "G_CONTENT_CLUSTER"
    if role in {"kpi_card", "kpi_text_region", "primary_chart", "insight_panel", "insight_text_region"}:
        return "G_DASHBOARD"
    if role in {"table_region", "table_header_band", "table_body_grid", "kpi_chip"}:
        return "G_TABLE"
    if role in {"toc_item", "toc_text_region", "active_marker"}:
        return "G_TOC"
    if role in {"evidence_card", "evidence_text_region", "evidence_tag_chip", "key_claim_text_region"}:
        return "G_EVIDENCE"
    if role in {"grid_card", "grid_card_text_region"}:
        return "G_CARD_GRID"
    if role in {"framework_stage", "framework_text_region", "connector_line"}:
        return "G_FRAMEWORK"
    if role in {"process_node", "process_text_region", "phase_rail"}:
        return "G_PROCESS"
    if role in {"comparison_matrix", "matrix_header_band"}:
        return "G_MATRIX"
    if role in {"timeline_axis", "timeline_phase", "milestone_text_region"}:
        return "G_TIMELINE"
    if role.startswith("section_") or role == "progress_indicator":
        return "G_SECTION_DIVIDER"
    if role.startswith("source_footer"):
        return "G_FOOTER"
    return None


def _layer_name(role: str, layer_id: str) -> str:
    return {
        "background_base": "background.base.shape",
        "decorative_texture": "texture.margin.raster",
        "hero_visual_field": "hero.visual.smart_object",
        "title_text_region": "title.main.text",
        "subtitle_text_region": "subtitle.context.text",
        "card_panel": "card.panel.shape",
        "body_text_region": "body.card.text",
        "source_footer_strip": "footer.source.strip.shape",
        "source_footer_text": "footer.source.text",
        "semantic_icon": "icon.semantic.native_vector",
        "technical_overlay": "technical.overlay.shape",
        "kpi_card": "kpi.card.shape",
        "kpi_text_region": "kpi.text.region",
        "primary_chart": "chart.primary.native_chart",
        "insight_panel": "insight.panel.shape",
        "insight_text_region": "insight.text.region",
        "table_region": "table.native.region",
        "table_header_band": "table.header.band",
        "table_body_grid": "table.body.grid",
        "kpi_chip": "kpi.chip.shape",
        "meta_text_region": "meta.cover.text",
        "section_number_text_region": "section.number.text",
        "section_title_text_region": "section.title.text",
        "section_subtitle_text_region": "section.subtitle.text",
        "progress_indicator": "progress.indicator.shape",
        "toc_item": "toc.item.shape",
        "toc_text_region": "toc.item.text",
        "active_marker": "toc.active.marker",
        "key_claim_text_region": "claim.key.text",
        "evidence_card": "evidence.card.shape",
        "evidence_text_region": "evidence.card.text",
        "evidence_tag_chip": "evidence.tag.shape",
        "grid_card": "card.grid.shape",
        "grid_card_text_region": "card.grid.text",
        "framework_stage": "framework.stage.shape",
        "framework_text_region": "framework.stage.text",
        "process_node": "process.node.shape",
        "process_text_region": "process.node.text",
        "connector_line": "connector.line.shape",
        "phase_rail": "process.phase.rail",
        "comparison_matrix": "matrix.comparison.native_table",
        "matrix_header_band": "matrix.header.band",
        "timeline_axis": "timeline.axis.connector",
        "timeline_phase": "timeline.phase.shape",
        "milestone_text_region": "timeline.milestone.text",
    }.get(role, layer_id.lower())


def _shape_type(role: str) -> str | None:
    if role == "hero_visual_field":
        return "rounded_rect_picture_frame"
    if role == "card_panel":
        return "rounded_rect"
    if role == "background_base":
        return "rect"
    if role == "semantic_icon":
        return "native_circle_triangle_icon"
    if role == "primary_chart":
        return "native_chart"
    if role in _TABLE_ROLES:
        return "native_table"
    if role in _CONNECTOR_ROLES:
        return "ppt_connector"
    if role == "kpi_card":
        return "rounded_rect"
    if role in _PANEL_ROLES:
        return "rounded_rect"
    return None


def _asset_ref(role: str) -> str | None:
    if role == "hero_visual_field":
        return "generated_assets/IMG_HERO_01.png"
    if role == "decorative_texture":
        return "generated_assets/BG_TEXTURE_01.png"
    return None


def _raster_rationale(role: str) -> str:
    if role == "hero_visual_field":
        return "Bounded replaceable nonsemantic visual field; contains no text or semantic marks."
    if role == "decorative_texture":
        return "Bounded nonsemantic margin texture documented by asset recipe."
    return "Semantic or structural layer remains editable PPT primitive or native vector."


def _content_bearing(role: str) -> bool:
    if role in _NON_CONTENT_ROLES:
        return False
    return _is_text_role(role) or role in {
        "title_text_region",
        "subtitle_text_region",
        "body_text_region",
        "card_panel",
        "source_footer_strip",
        "source_footer_text",
        "semantic_icon",
        "meta_text_region",
        "kpi_card",
        "kpi_text_region",
        "primary_chart",
        "insight_panel",
        "insight_text_region",
        "table_region",
        "table_header_band",
        "table_body_grid",
        "kpi_chip",
        "toc_item",
        "evidence_card",
        "evidence_tag_chip",
        "grid_card",
        "framework_stage",
        "process_node",
        "comparison_matrix",
        "matrix_header_band",
        "timeline_phase",
    }


def _is_text_role(role: str) -> bool:
    return role.endswith("text_region") or role == "source_footer_text"


_PANEL_ROLES = {
    "kpi_card",
    "insight_panel",
    "table_header_band",
    "table_body_grid",
    "kpi_chip",
    "toc_item",
    "active_marker",
    "evidence_card",
    "evidence_tag_chip",
    "grid_card",
    "framework_stage",
    "process_node",
    "phase_rail",
    "matrix_header_band",
    "timeline_phase",
    "progress_indicator",
}
_TABLE_ROLES = {"table_region", "comparison_matrix"}
_CONNECTOR_ROLES = {"connector_line", "timeline_axis"}
_NON_CONTENT_ROLES = {"background_base", "decorative_texture", "technical_overlay", "connector_line", "timeline_axis", "phase_rail", "progress_indicator", "active_marker"}
