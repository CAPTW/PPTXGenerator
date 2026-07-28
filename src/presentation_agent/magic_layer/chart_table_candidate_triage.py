"""D04 handoff candidate triage for chart/table promotion."""

from __future__ import annotations

from typing import Any


TRIAGE_CLASSES = {
    "true_chart_region",
    "true_table_region",
    "true_matrix_region",
    "chart_axis_or_legend",
    "table_header_or_cell_group",
    "connector_not_chart",
    "process_or_timeline_connector",
    "technical_overlay_not_data",
    "icon_marker_not_data",
    "decorative_nonsemantic",
    "text_region_handoff_D02",
    "unknown_requires_review",
}

DISPOSITIONS = {
    "promote_native_chart",
    "promote_editable_shape_chart",
    "promote_native_table",
    "promote_editable_shape_grid_table",
    "chart_axis_legend_handoff",
    "table_header_cell_handoff",
    "connector_keep_as_ppt_connector",
    "technical_overlay_keep_decorative",
    "icon_marker_handoff_D03",
    "text_handoff_D02",
    "unresolved_blocking",
    "unresolved_nonblocking_decorative",
}


def build_handoff_candidate_triage_policy() -> dict[str, Any]:
    return {
        "schema_name": "d04_handoff_candidate_triage_policy_v1",
        "status": "passed",
        "candidate_classes": sorted(TRIAGE_CLASSES),
        "triage_signals": [
            "candidate_bbox_size_and_aspect_ratio",
            "repeated_grid_like_alignment",
            "row_column_structure",
            "axis_legend_nearby_structure",
            "kpi_chart_table_archetype_context",
            "D02_text_slot_map",
            "D03_primitive_family",
            "z_order_relationship",
            "neighboring_connectors",
            "color_line_density",
            "confidence_and_source",
        ],
        "rules": [
            "D03 handoff candidate is not automatically a chart/table.",
            "Connector lines must not become charts.",
            "Technical overlays must not become data components.",
            "Table/chart-like semantic regions cannot remain final raster.",
            "Unknown chart/table candidates must be explicitly reported.",
        ],
    }


def triage_handoff_candidates(
    reference_id: str,
    handoff: dict[str, Any],
    primitive_mapping: dict[str, Any],
    manifest: dict[str, Any],
    text_slot_map: dict[str, Any],
) -> dict[str, Any]:
    primitive_by_layer = {}
    for primitive in primitive_mapping.get("primitive_mappings") or []:
        for layer_id in primitive.get("source_layer_ids") or []:
            primitive_by_layer[layer_id] = primitive
    layer_by_id = {layer["layer_id"]: layer for layer in manifest.get("layers") or []}
    triaged = []
    false_positives = []
    for candidate in handoff.get("candidates") or []:
        entry = _triage_candidate(reference_id, candidate, primitive_by_layer, layer_by_id, text_slot_map)
        triaged.append(entry)
        if entry["triage_class"] in {
            "connector_not_chart",
            "process_or_timeline_connector",
            "technical_overlay_not_data",
            "icon_marker_not_data",
            "decorative_nonsemantic",
            "text_region_handoff_D02",
        }:
            false_positives.append(entry)
    return {
        "schema_name": "handoff_candidate_triage",
        "reference_id": reference_id,
        "candidate_count": len(triaged),
        "triaged_candidates": triaged,
        "false_positive_count": len(false_positives),
        "false_positive_candidates": false_positives,
        "unresolved_blocking_count": sum(1 for item in triaged if item["final_disposition"] == "unresolved_blocking"),
    }


def validate_triage_entry(entry: dict[str, Any]) -> list[str]:
    required = {
        "candidate_id",
        "source_layer_ids",
        "bbox_px",
        "D03_candidate_type",
        "D03_primitive_family",
        "D03_semantic_role",
        "D02_text_slot_evidence",
        "triage_class",
        "confidence",
        "reason",
        "final_disposition",
    }
    errors = []
    missing = required.difference(entry)
    if missing:
        errors.append(f"missing_fields:{','.join(sorted(missing))}")
    if entry.get("triage_class") not in TRIAGE_CLASSES:
        errors.append(f"invalid_triage_class:{entry.get('triage_class')}")
    if entry.get("final_disposition") not in DISPOSITIONS:
        errors.append(f"invalid_final_disposition:{entry.get('final_disposition')}")
    if entry.get("triage_class") in {"connector_not_chart", "process_or_timeline_connector"} and entry.get("final_disposition") in {"promote_native_chart", "promote_editable_shape_chart"}:
        errors.append("connector_not_chart_cannot_promote_to_chart")
    if entry.get("triage_class") == "technical_overlay_not_data" and entry.get("final_disposition") in {"promote_native_table", "promote_editable_shape_grid_table"}:
        errors.append("technical_overlay_not_data_cannot_promote_to_table")
    return errors


def required_reference_gap(reference_id: str, chart_candidates: list[dict[str, Any]], table_candidates: list[dict[str, Any]]) -> str:
    if reference_id == "data_dashboard" and not chart_candidates:
        return "data_dashboard_chart_absence_requires_explicit_risk_or_blocker"
    if reference_id == "table_heavy" and not table_candidates:
        return "table_heavy_table_absence_requires_explicit_risk_or_blocker"
    return ""


def _triage_candidate(
    reference_id: str,
    candidate: dict[str, Any],
    primitive_by_layer: dict[str, dict[str, Any]],
    layer_by_id: dict[str, dict[str, Any]],
    text_slot_map: dict[str, Any],
) -> dict[str, Any]:
    layer_id = (candidate.get("source_layer_ids") or [""])[0]
    primitive = primitive_by_layer.get(layer_id, {})
    layer = layer_by_id.get(layer_id, {})
    bbox = candidate.get("bbox_px") or primitive.get("bbox_px") or layer.get("bbox_px") or [0, 0, 1, 1]
    family = primitive.get("primitive_family") or candidate.get("candidate_type") or "unknown"
    triage_class, disposition, reason = _classify(reference_id, family, layer, bbox)
    confidence = max(float(candidate.get("confidence") or 0), float(primitive.get("confidence") or 0), float(layer.get("confidence") or 0))
    if triage_class in {"true_chart_region", "true_table_region", "true_matrix_region"}:
        confidence = max(confidence, 0.66)
    return {
        "candidate_id": candidate.get("candidate_id"),
        "source_layer_ids": candidate.get("source_layer_ids") or [],
        "bbox_px": bbox,
        "bbox_norm": candidate.get("bbox_norm") or primitive.get("bbox_norm") or layer.get("bbox_norm"),
        "D03_candidate_type": candidate.get("candidate_type"),
        "D03_primitive_family": family,
        "D03_semantic_role": primitive.get("semantic_role") or layer.get("semantic_role"),
        "D02_text_slot_evidence": _text_slot_evidence(text_slot_map, bbox),
        "triage_class": triage_class,
        "confidence": round(min(0.95, confidence), 4),
        "reason": reason,
        "final_disposition": disposition,
    }


def _classify(reference_id: str, family: str, layer: dict[str, Any], bbox: list[int]) -> tuple[str, str, str]:
    _x, _y, w, h = [int(v) for v in bbox]
    aspect = w / h if h else 0.0
    area = w * h
    if family == "connector_line":
        return "connector_not_chart", "connector_keep_as_ppt_connector", "D03 family is connector_line; connectors are not promoted to chart/table data."
    if family == "technical_overlay":
        return "technical_overlay_not_data", "technical_overlay_keep_decorative", "Technical overlay remains decorative/editable shape, not a data component."
    if family == "accent_line":
        if reference_id == "data_dashboard":
            return "chart_axis_or_legend", "chart_axis_legend_handoff", "Wide accent/axis line near dashboard chart area."
        if reference_id == "table_heavy":
            return "table_header_or_cell_group", "table_header_cell_handoff", "Wide accent line likely belongs to table/grid chrome."
        return "decorative_nonsemantic", "unresolved_nonblocking_decorative", "Accent line is nonsemantic for D04."
    if family == "chart_frame":
        if reference_id == "data_dashboard" and area > 2500 and 0.35 <= aspect <= 2.4:
            return "true_chart_region", "promote_editable_shape_chart", "Dashboard chart marker cluster has chart-scale geometry."
        return "chart_axis_or_legend", "chart_axis_legend_handoff", "Chart-like marker is part of axis/legend/frame structure."
    if family in {"table_region", "matrix_region", "comparison_matrix_grid"}:
        if reference_id == "table_heavy" and area > 1800:
            return "true_table_region", "promote_editable_shape_grid_table", "Table-heavy marker cluster belongs to table/grid structure."
        if reference_id == "canva_benchmark" and area > 3500 and aspect > 1.8:
            return "true_matrix_region", "promote_editable_shape_grid_table", "Benchmark region has matrix-like aspect and scale."
        return "table_header_or_cell_group", "table_header_cell_handoff", "Table-like marker is treated as table header/cell structure."
    if family == "chart_region":
        return "true_chart_region", "promote_editable_shape_chart", "Explicit chart_region primitive."
    if family in {"callout_panel", "card_panel", "note_panel", "side_rail"}:
        return "icon_marker_not_data", "icon_marker_handoff_D03", "Panel/callout primitive is not promoted as a data component."
    if str(layer.get("layer_type")) == "icon_region":
        return "icon_marker_not_data", "icon_marker_handoff_D03", "Icon-like marker is not enough evidence for data semantics."
    return "unknown_requires_review", "unresolved_blocking", "No safe chart/table triage rule matched."


def _text_slot_evidence(text_slot_map: dict[str, Any], bbox: list[int]) -> dict[str, Any]:
    # D02 OCR is unavailable; this remains weak geometric slot context only.
    slot_counts = text_slot_map.get("slot_counts") or {}
    return {
        "ocr_text_available": False,
        "slot_counts": slot_counts,
        "evidence_strength": "weak_geometry_only",
        "bbox_px": bbox,
    }
