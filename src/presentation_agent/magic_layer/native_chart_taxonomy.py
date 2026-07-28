"""Native/editable chart taxonomy for Magic Layer D04."""

from __future__ import annotations

from typing import Any


CHART_COMPONENTS = {
    "kpi_bar_chart": (True, True, ["category", "value", "series"]),
    "line_trend_chart": (True, True, ["x_value", "y_value", "series"]),
    "bar_line_combo_chart": (True, True, ["category", "bar_value", "line_value"]),
    "donut_or_ring_summary": (True, True, ["segment", "value"]),
    "small_multiples_chart": (False, True, ["panel", "category", "value"]),
    "threshold_band_chart": (False, True, ["category", "value", "threshold"]),
    "scatter_or_signal_plot": (True, True, ["x_value", "y_value", "series"]),
    "axis_label_group": (False, True, ["axis_label"]),
    "legend_group": (False, True, ["legend_label", "series_key"]),
    "annotation_band": (False, True, ["annotation_label"]),
    "chart_frame_only": (False, True, ["chart_title", "source_data_ref"]),
    "unknown_chart_pending_review": (False, False, []),
}


def build_native_chart_component_taxonomy() -> dict[str, Any]:
    components = []
    for component, (native_possible, shape_possible, fields) in CHART_COMPONENTS.items():
        components.append(
            {
                "chart_component_type": component,
                "target_ppt_object_type": "native_ppt_chart" if native_possible else "editable_shape_chart",
                "native_ppt_chart_possible": native_possible,
                "editable_shape_chart_possible": shape_possible,
                "required_data_fields": fields,
                "label_fields": ["chart_title", "axis_labels", "legend_labels", "annotation_labels"],
                "axis_legend_policy": "editable_text_and_shape_groups",
                "source_citation_hooks": ["source_id", "citation_id", "data_range_ref"],
                "raster_final_use_policy": "forbidden_for_semantic_chart",
                "D05_render_fidelity_requirements": ["render_compare", "label_readability", "no_semantic_raster"],
            }
        )
    return {
        "schema_name": "native_chart_component_taxonomy_v1",
        "status": "passed",
        "components": components,
        "component_count": len(components),
    }


def chart_type_for_reference(reference_id: str) -> str:
    if reference_id == "data_dashboard":
        return "bar_line_combo_chart"
    if reference_id == "canva_benchmark":
        return "chart_frame_only"
    return "unknown_chart_pending_review"

