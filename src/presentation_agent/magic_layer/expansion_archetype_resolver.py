"""Build richer archetype-specific candidate specs for D06.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .editable_candidate_compiler import SLIDE_HEIGHT_IN, SLIDE_WIDTH_IN, validate_editable_candidate_spec


def build_d06_1_candidate_spec(
    *,
    reference_id: str,
    reference_image_path: Path,
    base_spec: dict[str, Any],
    source_manifest: dict[str, Any],
) -> dict[str, Any]:
    objects = [_background(reference_id)]
    objects.extend(_archetype_objects(reference_id, reference_image_path))
    objects.extend(_selected_text_slots(reference_id, base_spec))
    objects.extend(_selected_semantic_components(reference_id, base_spec))
    objects.sort(key=lambda item: int(item.get("z_order", 0)))
    spec = {
        "schema_name": "d06_1_editable_candidate_spec",
        "schema_version": "1.2",
        "reference_id": reference_id,
        "slide_size": {"width_in": SLIDE_WIDTH_IN, "height_in": SLIDE_HEIGHT_IN, "aspect_ratio": 16 / 9},
        "source_reference_image": reference_image_path.as_posix(),
        "source_reference_metadata": source_manifest.get("reference_metadata") or {},
        "reference_image_as_background": False,
        "screenshot_slide": False,
        "selected_route": "editable_candidate_magic_layer_d06_1_visual_recalibrated",
        "objects": objects,
        "fallbacks": [
            {
                "fallback_id": f"{reference_id}_ocr_unavailable_slot_labels",
                "recorded": True,
                "allowed": True,
                "reason": "OCR remains unavailable; D06.1 uses editable semantic slot labels only.",
            },
            {
                "fallback_id": f"{reference_id}_archetype_identity_skeleton_v2",
                "recorded": True,
                "allowed": True,
                "reason": "D06.1 uses explicit archetype-major-region skeletons to prevent generic block regression.",
            },
        ],
        "semantic_policy": {
            "semantic_text_target": "ppt_text",
            "semantic_icon_target": "svg_vector_or_ppt_vector_shape",
            "semantic_chart_target": "editable_shape_chart_skeleton",
            "semantic_table_target": "editable_shape_grid_table_skeleton",
            "semantic_raster_final_use_allowed": False,
            "full_slide_reference_background_allowed": False,
            "screenshot_slide_allowed": False,
        },
        "source_manifest_schema": source_manifest.get("schema_name"),
        "compile_status": "ready",
        "canva_parity_claimed": False,
    }
    errors = validate_editable_candidate_spec(spec)
    spec["validation_errors"] = errors
    if errors:
        spec["compile_status"] = "blocked"
    return spec


def _background(reference_id: str) -> dict[str, Any]:
    return {
        "object_id": f"{reference_id}_bg",
        "object_type": "ppt_shape",
        "primitive_family": "background_base",
        "semantic_component": "background",
        "identity_region": "background_base",
        "component_identity": "background_base",
        "bbox_norm": [0, 0, 1, 1],
        "z_order": 0,
        "final_use": "ppt_shape",
        "fill": "#07111F",
        "line": "#07111F",
        "editable": True,
    }


def _archetype_objects(reference_id: str, reference_image_path: Path) -> list[dict[str, Any]]:
    builders = {
        "cover_hero": _cover_hero,
        "standard_content": _standard_content,
        "data_dashboard": _data_dashboard,
        "table_heavy": _table_heavy,
        "section_divider": _section_divider,
        "visual_toc": _visual_toc,
        "evidence_overview": _evidence_overview,
        "card_grid": _card_grid,
        "methodology_framework": _methodology_framework,
        "process_flow": _process_flow,
        "comparison_matrix": _comparison_matrix,
        "timeline_roadmap": _timeline_roadmap,
        "decision_record": _decision_record,
        "risk_register": _risk_register,
        "case_study": _case_study,
        "closing_synthesis": _closing_synthesis,
    }
    return builders.get(reference_id, _standard_content)(reference_id, reference_image_path)


def _cover_hero(rid: str, ref: Path) -> list[dict[str, Any]]:
    return [
        _crop(rid, "hero_field", "hero_visual_field", [0.45, 0.02, 0.53, 0.82], ref, "hero_visual_field", "hero_visual_field", 20),
        _shape(rid, "title_slab", [0.05, 0.24, 0.34, 0.32], "title_cluster", "editorial_title_cluster", "#0B1528", "#38BDF8", 70),
        _shape(rid, "meta_strip", [0.05, 0.61, 0.31, 0.10], "meta_strip", "cover_meta", "#082F49", "#38BDF8", 75),
        _footer(rid),
    ]


def _standard_content(rid: str, ref: Path) -> list[dict[str, Any]]:
    return [
        _title_band(rid),
        *_cards(rid, "content_card", 0.06, 0.28, 0.25, 0.19, 2, 2, "card_panel_group"),
        _shape(rid, "insight_rail", [0.72, 0.20, 0.22, 0.58], "right_side_rail", "insight_rail", "#102A43", "#F59E0B", 75),
        _footer(rid),
    ]


def _data_dashboard(rid: str, ref: Path) -> list[dict[str, Any]]:
    return [
        _title_band(rid),
        *_cards(rid, "kpi_card", 0.05, 0.18, 0.20, 0.10, 4, 1, "kpi_row"),
        _chart(rid, "main_chart", [0.05, 0.34, 0.56, 0.37], "chart_frame"),
        _shape(rid, "insight_panel", [0.66, 0.34, 0.28, 0.37], "right_side_rail", "dashboard_insight_panel", "#F8FAFC", "#CBD5E1", 70),
        _footer(rid),
    ]


def _table_heavy(rid: str, ref: Path) -> list[dict[str, Any]]:
    return [_title_band(rid), _table(rid, "main_table", [0.05, 0.20, 0.72, 0.55], "table_frame", rows=7, cols=5), _shape(rid, "side_rail", [0.80, 0.20, 0.15, 0.55], "right_side_rail", "table_side_rail", "#102A43", "#F59E0B", 70), _footer(rid)]


def _section_divider(rid: str, ref: Path) -> list[dict[str, Any]]:
    return [_crop(rid, "chapter_visual", "hero_visual_field", [0.00, 0.00, 0.42, 0.86], ref, "hero_visual_field", "chapter_visual", 20), _shape(rid, "section_number", [0.08, 0.26, 0.18, 0.22], "section_number", "section_number", "#111827", "#F59E0B", 70), _shape(rid, "title_slab", [0.48, 0.28, 0.42, 0.27], "title_cluster", "section_title_slab", "#F8FAFC", "#F59E0B", 65), _shape(rid, "chapter_marker", [0.48, 0.16, 0.18, 0.06], "chapter_marker", "chapter_marker", "#082F49", "#F59E0B", 75), _footer(rid)]


def _visual_toc(rid: str, ref: Path) -> list[dict[str, Any]]:
    objs = [_title_band(rid)]
    for i in range(6):
        objs.append(_shape(rid, f"nav_module_{i+1}", [0.07 + i * 0.135, 0.34, 0.105, 0.30], "navigation_modules", "toc_module", "#0F2942" if i != 1 else "#F59E0B", "#38BDF8", 80))
    objs.extend([_shape(rid, "active_path", [0.06, 0.27, 0.84, 0.035], "active_path", "toc_active_path", "#38BDF8", "#38BDF8", 76), _shape(rid, "side_meta", [0.82, 0.20, 0.13, 0.55], "side_meta_rail", "toc_side_rail", "#102A43", "#F59E0B", 70), _footer(rid)])
    return objs


def _evidence_overview(rid: str, ref: Path) -> list[dict[str, Any]]:
    return [_title_band(rid), *_cards(rid, "evidence_card", 0.05, 0.24, 0.18, 0.25, 3, 2, "evidence_cards"), _shape(rid, "confidence_module", [0.76, 0.24, 0.18, 0.50], "confidence_module", "confidence_rail", "#102A43", "#F59E0B", 70), _shape(rid, "bottom_insight", [0.05, 0.77, 0.89, 0.08], "bottom_insight_strip", "evidence_insight_strip", "#F8FAFC", "#CBD5E1", 70), _footer(rid)]


def _card_grid(rid: str, ref: Path) -> list[dict[str, Any]]:
    return [_title_band(rid), *_cards(rid, "capability_card", 0.06, 0.22, 0.20, 0.18, 4, 2, "multi_card_grid"), _shape(rid, "category_label", [0.06, 0.16, 0.60, 0.045], "category_labels", "card_category_label", "#082F49", "#38BDF8", 75), _shape(rid, "insight_strip", [0.06, 0.80, 0.86, 0.06], "insight_strip", "card_grid_insight", "#F8FAFC", "#F59E0B", 70), _footer(rid)]


def _methodology_framework(rid: str, ref: Path) -> list[dict[str, Any]]:
    objs = [_title_band(rid)]
    for i in range(5):
        objs.append(_shape(rid, f"framework_layer_{i+1}", [0.12, 0.22 + i * 0.095, 0.54, 0.065], "framework_layers", "framework_layer", "#F8FAFC", "#38BDF8" if i % 2 else "#F59E0B", 78))
        if i < 4:
            objs.append(_connector(rid, f"framework_connector_{i+1}", [0.38, 0.285 + i * 0.095, 0.03, 0.04], "connectors"))
    objs.extend([_shape(rid, "side_note", [0.73, 0.24, 0.18, 0.46], "side_note", "framework_side_note", "#102A43", "#F59E0B", 72), _footer(rid)])
    return objs


def _process_flow(rid: str, ref: Path) -> list[dict[str, Any]]:
    objs = [_title_band(rid), _shape(rid, "note_rail", [0.80, 0.22, 0.14, 0.48], "note_rail", "process_note_rail", "#102A43", "#F59E0B", 70)]
    for i in range(6):
        objs.append(_shape(rid, f"process_node_{i+1}", [0.07 + i * 0.11, 0.38, 0.075, 0.15], "process_nodes", "process_node", "#F8FAFC", "#38BDF8", 80))
        if i < 5:
            objs.append(_connector(rid, f"process_connector_{i+1}", [0.145 + i * 0.11, 0.445, 0.055, 0.02], "connectors"))
    objs.append(_shape(rid, "decision_point", [0.38, 0.57, 0.08, 0.08], "decision_points", "process_decision", "#F59E0B", "#F59E0B", 82, shape="diamond"))
    objs.append(_footer(rid))
    return objs


def _comparison_matrix(rid: str, ref: Path) -> list[dict[str, Any]]:
    return [_title_band(rid), _table(rid, "matrix", [0.05, 0.22, 0.68, 0.52], "matrix_grid", rows=5, cols=4), _shape(rid, "option_headers", [0.17, 0.17, 0.50, 0.045], "option_headers", "matrix_headers", "#082F49", "#38BDF8", 75), _shape(rid, "decision_rail", [0.77, 0.22, 0.17, 0.52], "decision_rail", "matrix_decision_rail", "#102A43", "#F59E0B", 70), _footer(rid)]


def _timeline_roadmap(rid: str, ref: Path) -> list[dict[str, Any]]:
    objs = [_title_band(rid), _connector(rid, "timeline_line", [0.08, 0.41, 0.80, 0.02], "timeline_line")]
    for i in range(6):
        objs.append(_shape(rid, f"phase_{i+1}", [0.08 + i * 0.13, 0.28, 0.10, 0.24], "phases", "timeline_phase", "#F8FAFC", "#38BDF8", 78))
        objs.append(_shape(rid, f"milestone_{i+1}", [0.10 + i * 0.13, 0.55, 0.045, 0.055], "milestones", "timeline_milestone", "#F59E0B", "#F59E0B", 82, shape="oval"))
    objs.append(_footer(rid))
    return objs


def _decision_record(rid: str, ref: Path) -> list[dict[str, Any]]:
    return [_title_band(rid), _shape(rid, "decision_stamp", [0.06, 0.22, 0.16, 0.22], "decision_stamp", "decision_stamp", "#102A43", "#F59E0B", 80, shape="oval"), _shape(rid, "record_panel", [0.25, 0.22, 0.36, 0.44], "record_panel", "decision_record_panel", "#F8FAFC", "#CBD5E1", 70), *_cards(rid, "status_module", 0.65, 0.22, 0.13, 0.12, 2, 2, "status_modules"), _shape(rid, "evidence_strip", [0.06, 0.72, 0.86, 0.08], "evidence_strip", "decision_evidence_strip", "#F8FAFC", "#F59E0B", 70), _footer(rid)]


def _risk_register(rid: str, ref: Path) -> list[dict[str, Any]]:
    return [_title_band(rid), _table(rid, "risk_table", [0.05, 0.20, 0.70, 0.56], "register_table", rows=7, cols=5), _shape(rid, "severity_fields", [0.77, 0.22, 0.08, 0.52], "severity_status_fields", "risk_severity", "#F59E0B", "#F59E0B", 75), _shape(rid, "side_meta", [0.86, 0.20, 0.09, 0.56], "side_meta_rail", "risk_side_meta", "#102A43", "#38BDF8", 70), _footer(rid)]


def _case_study(rid: str, ref: Path) -> list[dict[str, Any]]:
    return [_crop(rid, "case_image", "image_frame", [0.06, 0.22, 0.28, 0.42], ref, "image_frame", "case_image", 22), _title_band(rid), _shape(rid, "context_panel", [0.38, 0.22, 0.24, 0.20], "context_panel", "case_context", "#F8FAFC", "#CBD5E1", 70), _shape(rid, "evidence_panel", [0.65, 0.22, 0.28, 0.20], "evidence_panel", "case_evidence", "#F8FAFC", "#38BDF8", 70), _shape(rid, "result_panel", [0.38, 0.48, 0.55, 0.16], "result_panel", "case_result", "#102A43", "#F59E0B", 70), _footer(rid)]


def _closing_synthesis(rid: str, ref: Path) -> list[dict[str, Any]]:
    return [_title_band(rid), _shape(rid, "recommendation", [0.08, 0.24, 0.36, 0.30], "recommendation", "closing_recommendation", "#F8FAFC", "#F59E0B", 75), _shape(rid, "next_action", [0.48, 0.24, 0.20, 0.30], "next_action", "closing_next_action", "#102A43", "#38BDF8", 75), _shape(rid, "evidence_summary", [0.08, 0.61, 0.60, 0.12], "evidence_summary", "closing_evidence", "#F8FAFC", "#CBD5E1", 70), _shape(rid, "decision_takeaway", [0.72, 0.24, 0.20, 0.49], "decision_takeaway", "closing_takeaway", "#F59E0B", "#F59E0B", 80), _footer(rid)]


def _selected_text_slots(reference_id: str, base_spec: dict[str, Any]) -> list[dict[str, Any]]:
    slots = [obj for obj in base_spec.get("objects") or [] if obj.get("object_type") == "ppt_text"]
    selected = []
    seen = set()
    for obj in slots:
        slot = obj.get("slot_type") or "body"
        if slot in seen and slot not in {"body", "card_title", "source"}:
            continue
        if slot == "decorative_microtext":
            continue
        new = {**obj}
        new["object_id"] = f"{reference_id}_d06_1_text_{len(selected)+1:02d}"
        new["z_order"] = 900 + len(selected)
        new["text_color"] = "#F8FAFC" if slot in {"title", "subtitle", "source", "footer"} else "#0F172A"
        selected.append(new)
        seen.add(slot)
        if len(selected) >= 7:
            break
    if not any(obj.get("slot_type") == "title" for obj in selected):
        selected.append(_text(reference_id, "title", [0.06, 0.08, 0.30, 0.07], "TITLE", 24, "#F8FAFC"))
    if not any(obj.get("slot_type") in {"source", "footer"} for obj in selected):
        selected.append(_text(reference_id, "source", [0.05, 0.90, 0.35, 0.035], "SOURCE", 7, "#CBD5E1"))
    return selected


def _selected_semantic_components(reference_id: str, base_spec: dict[str, Any]) -> list[dict[str, Any]]:
    selected = []
    for obj in base_spec.get("objects") or []:
        if obj.get("semantic_component") == "icon":
            if len(selected) >= 3:
                continue
            new = {**obj}
            new["object_id"] = f"{reference_id}_d06_1_icon_{len(selected)+1:02d}"
            new["bbox_norm"] = _small_icon_bbox(reference_id, len(selected))
            new["placeholder_marker"] = True
            new["integrated_marker"] = True
            new["icon_shape"] = "oval"
            new["z_order"] = 820 + len(selected)
            selected.append(new)
    return selected


def _small_icon_bbox(reference_id: str, index: int) -> list[float]:
    return [0.06 + index * 0.035, 0.16, 0.022, 0.038]


def _title_band(rid: str) -> dict[str, Any]:
    return _shape(rid, "title_band", [0.05, 0.06, 0.55, 0.105], "title_cluster", "title_band", "#0B1528", "#38BDF8", 70)


def _footer(rid: str) -> dict[str, Any]:
    return _shape(rid, "footer_source_strip", [0.03, 0.885, 0.94, 0.07], "bottom_footer_source_strip", "source_footer_strip", "#0F172A", "#38BDF8", 80)


def _cards(rid: str, prefix: str, x: float, y: float, w: float, h: float, cols: int, rows: int, identity: str) -> list[dict[str, Any]]:
    cards = []
    gap_x = 0.025
    gap_y = 0.035
    for row in range(rows):
        for col in range(cols):
            cards.append(_shape(rid, f"{prefix}_{row+1}_{col+1}", [x + col * (w + gap_x), y + row * (h + gap_y), w, h], identity, prefix, "#F8FAFC", "#CBD5E1", 78))
    return cards


def _shape(rid: str, oid: str, bbox: list[float], identity: str, component: str, fill: str, line: str, z: int, *, shape: str = "rect") -> dict[str, Any]:
    return {
        "object_id": f"{rid}_{oid}",
        "object_type": "ppt_shape",
        "primitive_family": component,
        "semantic_component": "source_footer" if identity == "bottom_footer_source_strip" else "major_region",
        "identity_region": identity,
        "component_identity": component,
        "bbox_norm": bbox,
        "z_order": z,
        "final_use": "ppt_shape",
        "fill": fill,
        "line": line,
        "editable": True,
        "shape": shape,
    }


def _crop(rid: str, oid: str, identity: str, bbox: list[float], ref: Path, primitive: str, component: str, z: int) -> dict[str, Any]:
    return {
        "object_id": f"{rid}_{oid}",
        "object_type": "scoped_visual_field_crop",
        "primitive_family": primitive,
        "semantic_component": "visual_field",
        "identity_region": identity,
        "component_identity": component,
        "bbox_norm": bbox,
        "source_crop_bbox_norm": bbox,
        "z_order": z,
        "final_use": "allowed_scoped_visual_field_raster",
        "editable": True,
        "source": "D06_1_archetype_visual_field",
    }


def _connector(rid: str, oid: str, bbox: list[float], identity: str) -> dict[str, Any]:
    return {
        "object_id": f"{rid}_{oid}",
        "object_type": "ppt_connector",
        "primitive_family": "connector_line",
        "semantic_component": "major_region",
        "identity_region": identity,
        "component_identity": "connector",
        "bbox_norm": bbox,
        "z_order": 84,
        "final_use": "ppt_shape",
        "line": "#38BDF8",
        "editable": True,
    }


def _chart(rid: str, oid: str, bbox: list[float], identity: str) -> dict[str, Any]:
    return {
        "object_id": f"{rid}_{oid}",
        "object_type": "editable_shape_chart",
        "primitive_family": "chart_region",
        "semantic_component": "chart",
        "identity_region": identity,
        "component_identity": "editable_chart_skeleton",
        "bbox_norm": bbox,
        "z_order": 85,
        "final_use": "editable_shape_chart",
        "editable": True,
    }


def _table(rid: str, oid: str, bbox: list[float], identity: str, *, rows: int, cols: int) -> dict[str, Any]:
    return {
        "object_id": f"{rid}_{oid}",
        "object_type": "editable_shape_grid_table",
        "primitive_family": "table_region",
        "semantic_component": "table",
        "identity_region": identity,
        "component_identity": "editable_table_grid",
        "bbox_norm": bbox,
        "z_order": 85,
        "final_use": "editable_shape_grid_table",
        "editable": True,
        "row_count": rows,
        "column_count": cols,
    }


def _text(rid: str, slot: str, bbox: list[float], text: str, size: int, color: str) -> dict[str, Any]:
    return {
        "object_id": f"{rid}_fallback_text_{slot}",
        "object_type": "ppt_text",
        "semantic_component": "text",
        "slot_type": slot,
        "primitive_family": "title_text_region" if slot == "title" else "body_text_region",
        "text": text,
        "bbox_norm": bbox,
        "z_order": 920,
        "font_size": size,
        "font_weight": "bold" if slot == "title" else "regular",
        "text_color": color,
        "editable": True,
        "final_use": "ppt_text",
    }
