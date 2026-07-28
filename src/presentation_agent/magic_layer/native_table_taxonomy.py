"""Native/editable table taxonomy for Magic Layer D04."""

from __future__ import annotations

from typing import Any


TABLE_COMPONENTS = {
    "native_ppt_table": (True, True, "general table with editable cells"),
    "editable_shape_grid_table": (False, True, "shape-grid table when native table styling is insufficient"),
    "comparison_matrix_grid": (False, True, "criteria/options matrix"),
    "risk_register_grid": (False, True, "risk register with severity/status metadata"),
    "evidence_inventory_table": (True, True, "evidence rows with source/citation metadata"),
    "traceability_metadata_header": (False, True, "metadata header chrome"),
    "table_header_band": (False, True, "editable header band"),
    "grouped_row_separator": (False, True, "editable row separator"),
    "side_rail_marker": (False, True, "editable table side rail"),
    "emphasis_cell": (False, True, "editable emphasis cell"),
    "citation_column": (True, True, "source/citation column"),
    "unknown_table_pending_review": (False, False, "unresolved table-like region"),
}


def build_native_table_component_taxonomy() -> dict[str, Any]:
    components = []
    for component, (native_possible, shape_possible, description) in TABLE_COMPONENTS.items():
        components.append(
            {
                "table_component_type": component,
                "target_ppt_object_type": "native_ppt_table" if native_possible else "editable_shape_grid_table",
                "native_ppt_table_possible": native_possible,
                "editable_shape_grid_possible": shape_possible,
                "row_column_capacity": {"min_rows": 2, "max_rows": 8, "min_columns": 2, "max_columns": 6},
                "header_body_citation_policy": "headers/body/citations remain editable text or native table cells",
                "source_citation_hooks": ["source_id", "citation_id", "row_source_ref", "cell_source_ref"],
                "raster_final_use_policy": "forbidden_for_semantic_table",
                "D05_render_fidelity_requirements": ["render_compare", "cell_readability", "no_semantic_raster"],
                "description": description,
            }
        )
    return {
        "schema_name": "native_table_component_taxonomy_v1",
        "status": "passed",
        "components": components,
        "component_count": len(components),
    }


def table_type_for_reference(reference_id: str) -> str:
    if reference_id == "table_heavy":
        return "evidence_inventory_table"
    if reference_id == "canva_benchmark":
        return "comparison_matrix_grid"
    return "unknown_table_pending_review"

