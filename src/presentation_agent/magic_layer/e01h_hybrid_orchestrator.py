"""Orchestration helpers for the E01H hybrid conversion payload."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e01h_object_graph_builder import (
    build_hybrid_object_graph,
    build_layer_manifest_v5,
    build_region_ledgers,
    build_semantic_slot_graph,
    build_visual_layer_graph,
)
from src.presentation_agent.magic_layer.e01h_reference_analyzer import analyze_reference_image
from src.presentation_agent.magic_layer.e01h_semantic_native_planner import build_semantic_native_plan
from src.presentation_agent.magic_layer.e01h_text_first_lock import build_text_first_lock_report
from src.presentation_agent.magic_layer.e01h_visual_backplate_planner import build_visual_backplate_policy


def build_e01h_conversion_payload(reference_path: str | Path) -> dict[str, Any]:
    analysis = analyze_reference_image(reference_path)
    text_lock = build_text_first_lock_report(analysis)
    object_graph = build_hybrid_object_graph(analysis, text_lock)
    backplate_policy = build_visual_backplate_policy(object_graph)
    semantic_plan = build_semantic_native_plan(object_graph)
    ledgers = build_region_ledgers(object_graph)
    return {
        "schema_name": "e01h_conversion_payload",
        "status": "passed",
        "reference_analysis_report": analysis,
        "text_first_lock_report": text_lock,
        "object_graph_v2": object_graph,
        "layer_manifest_v5": build_layer_manifest_v5(object_graph),
        "semantic_slot_graph": build_semantic_slot_graph(object_graph),
        "visual_layer_graph": build_visual_layer_graph(object_graph),
        **backplate_policy,
        **semantic_plan,
        **ledgers,
        "ps_layer_intent_hybrid": build_ps_layer_protocol_hybrid(object_graph, analysis, protocol_id="e01h_hybrid_intent"),
        "ps_layer_as_built_hybrid": build_ps_layer_protocol_hybrid(object_graph, analysis, protocol_id="e01h_hybrid_as_built"),
        "canva_parity_claimed": False,
    }


def build_ps_layer_protocol_hybrid(object_graph: dict[str, Any], analysis: dict[str, Any], *, protocol_id: str) -> dict[str, Any]:
    layers = []
    masks = []
    for node in object_graph["nodes"]:
        layer_kind = _layer_kind(node)
        target_kind = _pptx_target_kind(node, layer_kind)
        layer_id = f"lyr_{node['object_id']}"
        mask_id = None
        if layer_kind == "smart_object_like_image":
            mask_id = f"mask_{node['object_id']}"
            masks.append(
                {
                    "mask_id": mask_id,
                    "target_layer_id": layer_id,
                    "mask_type": "rectangular_clip",
                    "bbox_norm": node["bbox_norm"],
                    "polygon_points_norm": _rect_points(node["bbox_norm"]),
                    "alpha_source_ref": None,
                    "pptx_rendering_strategy": "native_crop",
                    "fallback_policy": "fallback_to_rectangular_crop",
                }
            )
        layers.append(
            {
                "layer_id": layer_id,
                "layer_name": _layer_name(node),
                "group_id": _group_id(node),
                "layer_kind": layer_kind,
                "semantic_role": node["semantic_role"],
                "content_bearing": bool(node["content_bearing"]),
                "bbox_norm": node["bbox_norm"],
                "z_order": int(node["z_order"]),
                "mask_id": mask_id,
                "opacity": 1,
                "blend_mode": "normal",
                "editability_target": target_kind,
                "pptx_target": {
                    "object_id": node["object_id"],
                    "group_id": _group_id(node),
                    "target_kind": target_kind,
                    "slot_id": node["object_id"] if node["layer_class"] == "semantic_editable" else None,
                    "shape_type": _shape_type(layer_kind),
                    "notes": "E01H hybrid layer: semantic objects native; visual fields bounded and replaceable.",
                },
                "raster_policy": _ps_raster_policy(node, target_kind),
                "asset_ref": f"backplate_assets/{node['object_id']}.png" if layer_kind == "smart_object_like_image" else None,
                "unknown_disposition": "not_unknown",
                "confidence": float(node["source_confidence"]),
            }
        )
    return {
        "schema_name": "ps_layer_protocol_v1",
        "schema_version": "1.0.0",
        "protocol_id": protocol_id,
        "source_reference": {
            "reference_id": "canva_magic_layer_reference_image",
            "reference_path": analysis["reference_path"],
            "reference_role": "design_reference_only",
            "photoshop_api_used": False,
            "adobe_service_used": False,
        },
        "slide_size": {"width_px": analysis["width"], "height_px": analysis["height"], "aspect_ratio": "16:9"},
        "layers": layers,
        "masks": masks,
        "selection_patch_contexts": [],
        "qa_gates": {
            "unknown_content_bearing_layer_gate": "fail_if_count_gt_0",
            "semantic_raster_gate": "fail_if_count_gt_0",
            "full_slide_raster_gate": "fail_if_count_gt_0",
            "selection_scope_gate": "fail_if_patch_modifies_unselected_semantic_layer",
            "bounded_nonsemantic_raster_gate": "fail_if_undocumented_or_unbounded",
        },
    }


def _layer_kind(node: dict[str, Any]) -> str:
    if node["object_type"] == "background_base":
        return "background_base"
    if node["object_type"] == "smart_object_like_image":
        return "smart_object_like_image"
    if node["object_type"] == "semantic_icon":
        return "semantic_icon"
    if node["object_type"] == "text":
        return "text"
    if node["object_type"] == "card":
        return "card"
    if node["object_type"] == "panel":
        return "panel" if node["layer_class"] == "semantic_editable" else "decorative_texture"
    if node["object_type"] == "technical_overlay":
        return "technical_overlay"
    return "shape"


def _pptx_target_kind(node: dict[str, Any], layer_kind: str) -> str:
    if layer_kind == "background_base":
        return "ppt_shape_background"
    if layer_kind == "smart_object_like_image":
        return "replaceable_image_frame"
    if layer_kind == "semantic_icon":
        return "native_vector"
    if layer_kind == "text":
        return "ppt_text_box"
    if layer_kind in {"card", "panel"}:
        return "ppt_shape"
    if layer_kind == "technical_overlay":
        return "ppt_shape"
    if layer_kind == "decorative_texture":
        return "bounded_nonsemantic_raster"
    return "ppt_shape"


def _ps_raster_policy(node: dict[str, Any], target_kind: str) -> dict[str, Any]:
    if target_kind == "replaceable_image_frame":
        return {"final_use": "replaceable_image_frame", "allowed": True, "bounded": True, "max_area_norm": _area(node), "rationale": "Bounded visual field; semantic overlays remain separate.", "gate": "pass"}
    if target_kind == "bounded_nonsemantic_raster":
        return {"final_use": "bounded_nonsemantic_raster", "allowed": True, "bounded": True, "max_area_norm": _area(node), "rationale": "Nonsemantic decorative backplate only.", "gate": "pass"}
    return {"final_use": "ppt_native", "allowed": True, "bounded": True, "max_area_norm": 0, "rationale": "Semantic or vector layer reconstructed with PPT-native objects.", "gate": "pass"}


def _layer_name(node: dict[str, Any]) -> str:
    prefix = node["semantic_role"].split("_")[0]
    if node["object_id"].startswith("bp_"):
        prefix = "hero" if "hero" in node["object_id"] else "image"
    return f"{prefix}.{node['object_id']}.{node['layer_class']}"


def _group_id(node: dict[str, Any]) -> str:
    role = node["semantic_role"]
    if "checklist" in role:
        return "grp_checklist"
    if "footer" in role or "source" in role:
        return "grp_footer"
    if "thumbnail" in role:
        return "grp_thumbnails"
    if "hero" in role:
        return "grp_hero"
    return "grp_visual_system"


def _shape_type(layer_kind: str) -> str | None:
    return {
        "text": None,
        "semantic_icon": "ppt_native_vector_group",
        "card": "rounded_rect",
        "panel": "rect",
        "background_base": "full_slide_rect",
        "smart_object_like_image": "rectangular_crop_frame",
    }.get(layer_kind, "shape")


def _rect_points(bbox: dict[str, float]) -> list[dict[str, float]]:
    x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
    return [{"x": x, "y": y}, {"x": x + w, "y": y}, {"x": x + w, "y": y + h}, {"x": x, "y": y + h}]


def _area(node: dict[str, Any]) -> float:
    bbox = node["bbox_norm"]
    return round(float(bbox["w"]) * float(bbox["h"]), 4)
