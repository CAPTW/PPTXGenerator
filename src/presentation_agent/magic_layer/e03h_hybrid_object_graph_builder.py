"""E03H object-graph definitions, extending the E02H hybrid primitives."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e02h_hybrid_object_graph_builder import (
    build_e02h_hybrid_object_graph,
    build_e02h_layer_manifest_v5,
    build_e02h_reference_definition,
    build_e02h_region_ledgers,
    build_e02h_semantic_slot_graph,
    build_e02h_visual_layer_graph,
)
from src.presentation_agent.magic_layer.e02h_reference_registry import build_e02h_reference_registry
from src.presentation_agent.magic_layer.e03h_reference_registry import build_e03h_reference_pack_registry


E02H_IDS = set(build_e02h_reference_registry())


def build_e03h_reference_definition(reference_id: str) -> dict[str, Any]:
    if reference_id in E02H_IDS:
        definition = build_e02h_reference_definition(reference_id)
        definition["reference_source"] = "e02h_regression"
        return definition
    registry = build_e03h_reference_pack_registry(include_optional=True)
    if reference_id not in registry:
        raise KeyError(f"unknown E03H reference id: {reference_id}")
    reference = registry[reference_id]
    return _definition(reference)


def build_e03h_hybrid_object_graph(definition: dict[str, Any], text_lock_report: dict[str, Any]) -> dict[str, Any]:
    graph = build_e02h_hybrid_object_graph(definition, text_lock_report)
    graph["schema_name"] = "object_graph_v2"
    return graph


build_e03h_layer_manifest_v5 = build_e02h_layer_manifest_v5
build_e03h_semantic_slot_graph = build_e02h_semantic_slot_graph
build_e03h_visual_layer_graph = build_e02h_visual_layer_graph
build_e03h_region_ledgers = build_e02h_region_ledgers


def _definition(reference: dict[str, Any]) -> dict[str, Any]:
    rows = [_region("bg_base", "background_base", [0, 0, 1, 1], "decorative_vector", "background_base", 0)]
    reference_id = reference["reference_id"]
    rows.extend(_common_title_footer(reference_id))
    if reference_id == "cover_hero_photo_editorial":
        rows.extend(_cover_regions())
    elif reference_id == "standard_content_card_cluster":
        rows.extend(_card_cluster_regions())
    elif reference_id == "evidence_stack_visual":
        rows.extend(_evidence_regions())
    elif reference_id == "comparison_matrix_hybrid":
        rows.extend(_comparison_regions())
    elif reference_id == "methodology_framework_layered":
        rows.extend(_methodology_regions())
    elif reference_id == "timeline_roadmap_hybrid":
        rows.extend(_timeline_regions())
    elif reference_id == "visual_toc_navigation":
        rows.extend(_toc_regions())
    elif reference_id == "photo_caption_grid_hybrid":
        rows.extend(_photo_grid_regions())
    else:
        rows.extend(_card_cluster_regions())
    return {
        **reference,
        "display_name": reference_id.replace("_", " ").title(),
        "canvas": {"width_px": 1600, "height_px": 900, "aspect_ratio": "16:9"},
        "style_tokens": {"palette": ["#041826", "#092D37", "#39D4E7", "#F3A51A", "#F3F7FA"], "tone": "e03h_high_fidelity_hybrid"},
        "regions": rows,
    }


def _common_title_footer(reference_id: str) -> list[dict[str, Any]]:
    title = reference_id.replace("_", " ").title()
    return [
        _region("title_text", "title_text", [0.055, 0.055, 0.66, 0.07], "semantic_editable", "text", 50, text=title, content=True),
        _region("footer_source_text", "footer_source_text", [0.055, 0.86, 0.80, 0.04], "semantic_editable", "text", 180, text=f"Source: {title} reference fixture", content=True),
    ]


def _cover_regions() -> list[dict[str, Any]]:
    return [
        _region("bp_hero_photo", "hero_visual_field", [0.05, 0.18, 0.56, 0.56], "replaceable_visual_field", "smart_object_like_image", 5),
        _region("bp_editorial_texture", "decorative_texture", [0.64, 0.16, 0.27, 0.60], "nonsemantic_visual_backplate", "decorative_texture", 6),
        _region("subtitle_text", "subtitle_text", [0.66, 0.28, 0.22, 0.11], "semantic_editable", "text", 90, text="A premium reference frame with protected copy", content=True),
        _region("hero_icon_1", "semantic_icon", [0.68, 0.46, 0.045, 0.08], "semantic_vector", "semantic_icon", 100, content=True, glyph="shield"),
    ]


def _card_cluster_regions() -> list[dict[str, Any]]:
    rows = [_region("bp_card_texture", "decorative_texture", [0.04, 0.18, 0.72, 0.56], "nonsemantic_visual_backplate", "decorative_texture", 5)]
    for idx, label in enumerate(["Signal", "Decision", "Action"], start=1):
        x = 0.08 + (idx - 1) * 0.24
        rows.extend([
            _region(f"card_{idx}", "card_panel", [x, 0.32, 0.19, 0.30], "semantic_editable", "card", 60 + idx, content=True),
            _region(f"card_icon_{idx}", "semantic_icon", [x + 0.02, 0.36, 0.04, 0.07], "semantic_vector", "semantic_icon", 80 + idx, content=True, glyph=["gauge", "shield", "clipboard"][idx - 1]),
            _region(f"card_text_{idx}", "body_text", [x + 0.075, 0.36, 0.10, 0.12], "semantic_editable", "text", 100 + idx, text=label, content=True),
        ])
    return rows


def _evidence_regions() -> list[dict[str, Any]]:
    rows = [
        _region("bp_evidence_texture", "decorative_texture", [0.05, 0.17, 0.78, 0.60], "nonsemantic_visual_backplate", "decorative_texture", 5),
        _region("claim_text", "body_text", [0.08, 0.22, 0.36, 0.12], "semantic_editable", "text", 70, text="Claim: evidence needs traceable native layers", content=True),
    ]
    for idx in range(1, 4):
        y = 0.36 + (idx - 1) * 0.12
        rows.extend([
            _region(f"evidence_card_{idx}", "card_panel", [0.48, y, 0.32, 0.09], "semantic_editable", "card", 80 + idx, content=True),
            _region(f"evidence_text_{idx}", "body_text", [0.50, y + 0.02, 0.25, 0.04], "semantic_editable", "text", 100 + idx, text=f"Evidence layer {idx}", content=True),
        ])
    return rows


def _comparison_regions() -> list[dict[str, Any]]:
    return [
        _region("bp_matrix_texture", "decorative_texture", [0.05, 0.18, 0.70, 0.58], "nonsemantic_visual_backplate", "decorative_texture", 5),
        _region("table_header_band", "table_header_band", [0.08, 0.22, 0.64, 0.08], "semantic_editable", "panel", 70, content=True),
        _region("table_matrix", "table_matrix", [0.08, 0.30, 0.64, 0.43], "semantic_native_component", "table", 90, content=True, target="native_table", data={"headers": ["Option", "Fit", "Risk", "Next"], "rows": [["A", "High", "Low", "Use"], ["B", "Med", "Med", "Watch"], ["C", "Low", "High", "Hold"]]}),
        _region("matrix_note", "insight_text", [0.78, 0.30, 0.14, 0.18], "semantic_editable", "text", 110, text="Matrix cells remain editable.", content=True),
    ]


def _methodology_regions() -> list[dict[str, Any]]:
    rows = [_region("bp_framework_texture", "decorative_texture", [0.05, 0.18, 0.78, 0.55], "nonsemantic_visual_backplate", "decorative_texture", 5)]
    for idx, label in enumerate(["Input", "Model", "Compile", "Validate"], start=1):
        y = 0.24 + (idx - 1) * 0.105
        rows.extend([
            _region(f"method_layer_{idx}", "process_node_panel", [0.16 + idx * 0.04, y, 0.46, 0.085], "semantic_editable", "card", 70 + idx, content=True),
            _region(f"method_text_{idx}", "process_node_text", [0.21 + idx * 0.04, y + 0.023, 0.25, 0.03], "semantic_editable", "text", 90 + idx, text=label, content=True),
        ])
        if idx < 4:
            rows.append(_region(f"method_connector_{idx}", "process_connector", [0.64, y + 0.07, 0.07, 0.035], "semantic_vector", "connector", 100 + idx, content=True, target="ppt_connector"))
    return rows


def _timeline_regions() -> list[dict[str, Any]]:
    rows = [_region("bp_timeline_texture", "decorative_texture", [0.05, 0.24, 0.82, 0.40], "nonsemantic_visual_backplate", "decorative_texture", 5)]
    for idx, label in enumerate(["Q1", "Q2", "Q3", "Q4", "Q5"], start=1):
        x = 0.10 + (idx - 1) * 0.16
        rows.extend([
            _region(f"milestone_{idx}", "timeline_milestone", [x, 0.41, 0.065, 0.11], "semantic_editable", "card", 70 + idx, content=True),
            _region(f"milestone_text_{idx}", "milestone_text", [x + 0.008, 0.45, 0.05, 0.03], "semantic_editable", "text", 90 + idx, text=label, content=True),
        ])
        if idx < 5:
            rows.append(_region(f"timeline_connector_{idx}", "timeline_connector", [x + 0.065, 0.455, 0.095, 0.02], "semantic_vector", "connector", 100 + idx, content=True, target="ppt_connector"))
    return rows


def _toc_regions() -> list[dict[str, Any]]:
    rows = [_region("bp_toc_texture", "decorative_texture", [0.05, 0.18, 0.78, 0.58], "nonsemantic_visual_backplate", "decorative_texture", 5)]
    for idx, label in enumerate(["Context", "Evidence", "System", "Decision", "Roadmap"], start=1):
        y = 0.22 + (idx - 1) * 0.10
        rows.extend([
            _region(f"toc_item_{idx}", "navigation_item", [0.16, y, 0.55, 0.07], "semantic_editable", "card", 70 + idx, content=True),
            _region(f"toc_icon_{idx}", "semantic_icon", [0.18, y + 0.013, 0.028, 0.05], "semantic_vector", "semantic_icon", 90 + idx, content=True, glyph="shield"),
            _region(f"toc_text_{idx}", "body_text", [0.23, y + 0.02, 0.20, 0.03], "semantic_editable", "text", 100 + idx, text=label, content=True),
        ])
    return rows


def _photo_grid_regions() -> list[dict[str, Any]]:
    rows = []
    for idx, label in enumerate(["Field", "Detail", "Team", "Evidence"], start=1):
        x = 0.08 + ((idx - 1) % 2) * 0.32
        y = 0.22 + ((idx - 1) // 2) * 0.25
        rows.extend([
            _region(f"photo_frame_{idx}", "thumbnail_visual_field", [x, y, 0.25, 0.17], "replaceable_visual_field", "smart_object_like_image", 50 + idx),
            _region(f"caption_{idx}", "thumbnail_caption_text", [x, y + 0.185, 0.22, 0.035], "semantic_editable", "text", 80 + idx, text=label, content=True),
        ])
    return rows


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
