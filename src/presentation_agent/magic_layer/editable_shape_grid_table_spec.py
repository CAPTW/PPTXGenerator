"""Editable shape-grid table spec builders for D04."""

from __future__ import annotations

from typing import Any


def build_editable_shape_grid_table_spec(reference_id: str, native_table_spec: dict[str, Any]) -> dict[str, Any]:
    specs = []
    for table in native_table_spec.get("table_specs") or []:
        skeleton = table["table_skeleton_spec"]
        specs.append(
            {
                "editable_shape_grid_table_spec_id": table["native_table_spec_id"].replace("native_table", "editable_shape_grid_table"),
                "source_native_table_spec_id": table["native_table_spec_id"],
                "reference_id": reference_id,
                "bbox_px": table["bbox_px"],
                "bbox_norm": table["bbox_norm"],
                "row_count_estimate": skeleton["row_count_inferred"],
                "column_count_estimate": skeleton["column_count_inferred"],
                "editable_primitives": ["ppt_shape_cells", "ppt_text_cell_labels", "ppt_shape_header_band", "ppt_shape_grid_lines"],
                "source_data_required_for_final_conversion": True,
                "raster_final_use_policy": "forbidden_for_semantic_table",
                "fallback_policy": "reject_or_patch_if_shape_grid_table_cannot_be_reconstructed",
            }
        )
    return {
        "schema_name": "editable_shape_grid_table_spec",
        "reference_id": reference_id,
        "status": "passed" if specs else "no_editable_shape_grid_table_spec",
        "table_specs": specs,
    }


def build_table_grid_structure_spec(reference_id: str, triage: dict[str, Any], native_table_spec: dict[str, Any]) -> dict[str, Any]:
    cell_items = [item for item in triage.get("triaged_candidates") or [] if item["triage_class"] == "table_header_or_cell_group"]
    table_specs = native_table_spec.get("table_specs") or []
    return {
        "schema_name": "table_grid_structure_spec",
        "reference_id": reference_id,
        "status": "passed" if table_specs or cell_items else "no_table_grid_detected",
        "table_grid_groups": [
            {
                "table_grid_spec_id": f"{reference_id}_table_grid_{index:02d}",
                "source_native_table_spec_id": table["native_table_spec_id"],
                "bbox_px": table["bbox_px"],
                "bbox_norm": table["bbox_norm"],
                "row_count_estimate": table["table_skeleton_spec"]["row_count_inferred"],
                "column_count_estimate": table["table_skeleton_spec"]["column_count_inferred"],
                "header_band_policy": "editable_shape_header_band",
                "cell_policy": "ppt_text_inside_shape_cells",
                "citation_column_policy": "source_data_required_later",
                "ocr_text_available": False,
            }
            for index, table in enumerate(table_specs, start=1)
        ],
        "header_cell_handoff_candidates": cell_items,
    }

