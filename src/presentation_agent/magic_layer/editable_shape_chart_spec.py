"""Editable shape chart spec builders for D04."""

from __future__ import annotations

from typing import Any


def build_editable_shape_chart_spec(reference_id: str, native_chart_spec: dict[str, Any]) -> dict[str, Any]:
    specs = []
    for chart in native_chart_spec.get("chart_specs") or []:
        specs.append(
            {
                "editable_shape_chart_spec_id": chart["native_chart_spec_id"].replace("native_chart", "editable_shape_chart"),
                "source_native_chart_spec_id": chart["native_chart_spec_id"],
                "reference_id": reference_id,
                "bbox_px": chart["bbox_px"],
                "bbox_norm": chart["bbox_norm"],
                "editable_primitives": ["ppt_shape_data_marks", "ppt_line_axes", "ppt_text_labels", "ppt_shape_legend"],
                "placeholder_data_fields": chart["chart_skeleton_spec"]["placeholder_data_fields"],
                "source_data_required_for_final_conversion": True,
                "raster_final_use_policy": "forbidden_for_semantic_chart",
                "fallback_policy": "reject_or_patch_if_shape_chart_cannot_be_reconstructed",
            }
        )
    return {
        "schema_name": "editable_shape_chart_spec",
        "reference_id": reference_id,
        "status": "passed" if specs else "no_editable_shape_chart_spec",
        "chart_specs": specs,
    }


def build_chart_axis_legend_spec(reference_id: str, triage: dict[str, Any]) -> dict[str, Any]:
    axis_items = [item for item in triage.get("triaged_candidates") or [] if item["triage_class"] == "chart_axis_or_legend"]
    return {
        "schema_name": "chart_axis_legend_spec",
        "reference_id": reference_id,
        "status": "passed" if axis_items else "no_axis_legend_detected",
        "axis_legend_groups": [
            {
                "axis_legend_spec_id": f"{reference_id}_axis_legend_{index:02d}",
                "source_candidate_id": item["candidate_id"],
                "source_layer_ids": item["source_layer_ids"],
                "bbox_px": item["bbox_px"],
                "bbox_norm": item["bbox_norm"],
                "target_ppt_object_type": "ppt_text_and_shape_group",
                "ocr_text_available": False,
                "label_policy": "slot_placeholder_until_source_data_binding",
                "tiny_label_risk": "D05_review_required" if item["bbox_px"][3] < 18 else "bounded",
            }
            for index, item in enumerate(axis_items, start=1)
        ],
    }

