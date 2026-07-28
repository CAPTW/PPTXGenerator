"""D04 chart/table handoff helpers for D03."""

from __future__ import annotations

from typing import Any


CHART_TABLE_FAMILIES = {
    "chart_region",
    "chart_frame",
    "legend_group",
    "axis_label_group",
    "table_region",
    "matrix_region",
    "comparison_matrix_grid",
}


def build_d04_handoff_candidates(reference_id: str, primitive_mapping: dict[str, Any], icon_resolution: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    for mapping in primitive_mapping.get("primitive_mappings") or []:
        if mapping.get("primitive_family") in CHART_TABLE_FAMILIES or mapping.get("handoff_stage") == "D04":
            candidates.append(_handoff_entry(reference_id, mapping, "primitive_mapping"))
    for icon in icon_resolution.get("svg_icon_mapping_candidates") or []:
        if icon.get("final_disposition") == "chart_table_marker_handoff_D04":
            candidates.append(
                {
                    "candidate_id": f"{reference_id}_d04_icon_{icon['layer_id']}",
                    "source_layer_ids": [icon["layer_id"]],
                    "candidate_type": "chart_table_marker",
                    "bbox_px": icon["bbox_px"],
                    "bbox_norm": icon["bbox_norm"],
                    "confidence": icon["mapping_confidence"],
                    "handoff_reason": "Icon-like region likely belongs to chart/table structure; D03 does not promote chart/table natively.",
                }
            )
    risk = ""
    if reference_id in {"data_dashboard", "table_heavy", "canva_benchmark"} and not candidates:
        risk = "expected_chart_table_like_regions_not_detected"
    return {
        "schema_name": "d04_chart_table_handoff_candidates",
        "reference_id": reference_id,
        "status": "passed_with_risk" if risk else "passed",
        "handoff_candidate_count": len(candidates),
        "candidates": candidates,
        "risk": risk,
        "d03_scope_note": "D03 records chart/table candidates only; D04 must promote native/editable components. Raster chart/table final use remains forbidden.",
    }


def _handoff_entry(reference_id: str, mapping: dict[str, Any], source: str) -> dict[str, Any]:
    family = mapping.get("primitive_family")
    candidate_type = {
        "chart_region": "chart_region",
        "chart_frame": "chart_frame",
        "table_region": "table_region",
        "matrix_region": "matrix_region",
        "comparison_matrix_grid": "comparison_matrix_grid",
    }.get(str(family), "chart_table_region")
    return {
        "candidate_id": f"{reference_id}_d04_{mapping['primitive_id']}",
        "source_layer_ids": mapping.get("source_layer_ids") or [],
        "candidate_type": candidate_type,
        "bbox_px": mapping.get("bbox_px"),
        "bbox_norm": mapping.get("bbox_norm"),
        "confidence": mapping.get("confidence"),
        "handoff_reason": "Primitive is chart/table-like or in a dashboard/table archetype and must be handled by D04.",
        "source": source,
    }

