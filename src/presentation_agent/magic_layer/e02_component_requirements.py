"""Native component requirements for the E02 archetype gate."""

from __future__ import annotations

from typing import Any


EDITABLE_CHART_TARGETS = {"native_chart", "editable_shape_chart"}
EDITABLE_TABLE_TARGETS = {"native_table", "editable_shape_grid_table"}
RASTER_TARGETS = {"bounded_nonsemantic_raster", "bounded_nonsemantic_texture", "raster", "not_applicable"}


def validate_component_requirements(archetype_id: str, native_reconstruction_plan: dict[str, Any], raster_report: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    actions = native_reconstruction_plan.get("actions", [])
    if int(raster_report.get("semantic_raster_violation_count", 0)) > 0:
        failures.append("semantic_raster_violation")
    if archetype_id == "data_dashboard":
        action = _find_action(actions, "primary_chart")
        if action is None or action.get("target_ppt_object_type") not in EDITABLE_CHART_TARGETS:
            failures.append("data_dashboard_primary_chart_not_editable")
        elif action.get("target_ppt_object_type") in RASTER_TARGETS:
            failures.append("data_dashboard_primary_chart_raster")
    if archetype_id == "table_heavy":
        action = _find_action(actions, "table_region")
        if action is None or action.get("target_ppt_object_type") not in EDITABLE_TABLE_TARGETS:
            failures.append("table_heavy_table_region_not_editable")
        elif action.get("target_ppt_object_type") in RASTER_TARGETS:
            failures.append("table_heavy_table_region_raster")
    if archetype_id == "comparison_matrix":
        action = _find_action(actions, "comparison_matrix")
        if action is None or action.get("target_ppt_object_type") not in EDITABLE_TABLE_TARGETS:
            failures.append("comparison_matrix_not_editable")
        elif action.get("target_ppt_object_type") in RASTER_TARGETS:
            failures.append("comparison_matrix_raster")
    decision = "passed" if not failures else "failed"
    if archetype_id not in {"data_dashboard", "table_heavy", "comparison_matrix"} and not failures:
        decision = "not_applicable"
    return {
        "schema_name": "e02_component_requirements_report",
        "archetype_id": archetype_id,
        "status": "passed" if not failures else "failed",
        "native_chart_table_decision": decision,
        "failures": failures,
        "canva_parity_claimed": False,
    }


def _find_action(actions: list[dict[str, Any]], semantic_role: str) -> dict[str, Any] | None:
    return next((action for action in actions if action.get("semantic_role") == semantic_role or action.get("source_object_id") == semantic_role), None)
