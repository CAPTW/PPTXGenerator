"""Resolve triaged chart regions into editable chart skeleton specs."""

from __future__ import annotations

from typing import Any

from .native_chart_taxonomy import chart_type_for_reference


def resolve_true_chart_regions(reference_id: str, triage: dict[str, Any]) -> dict[str, Any]:
    true_items = [item for item in triage.get("triaged_candidates") or [] if item["triage_class"] == "true_chart_region"]
    axis_items = [item for item in triage.get("triaged_candidates") or [] if item["triage_class"] == "chart_axis_or_legend"]
    chart_candidates = []
    if true_items:
        chart_candidates.append(_aggregate_chart_candidate(reference_id, true_items, axis_items))
    risk = ""
    if reference_id == "data_dashboard" and not chart_candidates:
        risk = "data_dashboard_chart_absence_requires_explicit_blocker"
    return {
        "schema_name": "true_chart_region_candidates",
        "reference_id": reference_id,
        "status": "passed" if chart_candidates else "no_chart_semantics_detected",
        "chart_candidates": chart_candidates,
        "axis_legend_candidates": axis_items,
        "risk": risk,
    }


def build_native_chart_spec(reference_id: str, chart_candidates: dict[str, Any]) -> dict[str, Any]:
    specs = []
    for index, candidate in enumerate(chart_candidates.get("chart_candidates") or [], start=1):
        chart_type = chart_type_for_reference(reference_id)
        specs.append(
            {
                "native_chart_spec_id": f"{reference_id}_native_chart_{index:02d}",
                "source_candidate_ids": candidate["source_candidate_ids"],
                "source_layer_ids": candidate["source_layer_ids"],
                "bbox_px": candidate["bbox_px"],
                "bbox_norm": candidate["bbox_norm"],
                "chart_component_type": chart_type,
                "target_ppt_object_type": "editable_shape_chart",
                "native_ppt_chart_possible": chart_type in {"kpi_bar_chart", "line_trend_chart", "bar_line_combo_chart", "donut_or_ring_summary", "scatter_or_signal_plot"},
                "editable_shape_chart_possible": True,
                "chart_skeleton_spec": {
                    "source_data_required_for_final_conversion": True,
                    "placeholder_data_fields": ["category", "value", "series"],
                    "data_values_inferred": False,
                    "unresolved_data_reason": "OCR unavailable and reference image is design input only; D04 will not fake chart data.",
                },
                "label_fields": ["chart_title", "axis_labels", "legend_labels", "annotation_labels"],
                "axis_legend_policy": "editable_text_and_shape_groups",
                "source_citation_hooks": ["source_id", "citation_id", "data_range_ref"],
                "raster_final_use_policy": "forbidden_for_semantic_chart",
                "D05_render_fidelity_requirements": ["render_compare", "label_readability", "no_semantic_chart_raster"],
            }
        )
    return {
        "schema_name": "native_chart_spec",
        "reference_id": reference_id,
        "status": "passed" if specs else "no_native_chart_spec",
        "chart_specs": specs,
        "risk": chart_candidates.get("risk") or "",
    }


def _aggregate_chart_candidate(reference_id: str, true_items: list[dict[str, Any]], axis_items: list[dict[str, Any]]) -> dict[str, Any]:
    source = true_items + axis_items
    return {
        "candidate_id": f"{reference_id}_chart_skeleton_01",
        "source_candidate_ids": [item["candidate_id"] for item in source],
        "source_layer_ids": sorted({layer_id for item in source for layer_id in item.get("source_layer_ids") or []}),
        "bbox_px": _union_bbox([item["bbox_px"] for item in source]),
        "bbox_norm": _union_bbox_norm([item.get("bbox_norm") for item in source if item.get("bbox_norm")]),
        "chart_component_type_candidate": chart_type_for_reference(reference_id),
        "confidence": round(sum(item["confidence"] for item in true_items) / len(true_items), 4),
        "data_values_inferred": False,
        "source_data_required_for_final_conversion": True,
    }


def _union_bbox(boxes: list[list[int]]) -> list[int]:
    x1 = min(box[0] for box in boxes)
    y1 = min(box[1] for box in boxes)
    x2 = max(box[0] + box[2] for box in boxes)
    y2 = max(box[1] + box[3] for box in boxes)
    return [x1, y1, x2 - x1, y2 - y1]


def _union_bbox_norm(boxes: list[list[float]]) -> list[float]:
    x1 = min(box[0] for box in boxes)
    y1 = min(box[1] for box in boxes)
    x2 = max(box[0] + box[2] for box in boxes)
    y2 = max(box[1] + box[3] for box in boxes)
    return [round(x1, 6), round(y1, 6), round(x2 - x1, 6), round(y2 - y1, 6)]

