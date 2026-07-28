"""E02 cross-archetype generalization guard."""

from __future__ import annotations

from typing import Any


def evaluate_e02_generalization_gate(archetype_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    signatures = [report.get("layout_signature") for report in archetype_reports.values()]
    if len(set(signatures)) == 1:
        failures.append("all_archetypes_share_layout_signature")
    if len(set(signatures)) < len(signatures):
        failures.append("layout_signature_reuse_detected")
    for archetype_id, report in archetype_reports.items():
        if report.get("status") != "passed":
            failures.append(f"{archetype_id}_failed")
        if report.get("visual_slot_fidelity_status") != "passed":
            failures.append(f"{archetype_id}_visual_slot_fidelity_failed")
        if report.get("e01p_v_postcompile_status") != "passed":
            failures.append(f"{archetype_id}_e01p_v_postcompile_failed")
        if int(report.get("semantic_raster_violation_count", 0)) > 0:
            failures.append(f"{archetype_id}_semantic_raster_violation")
        if int(report.get("unknown_content_bearing_count", 0)) > 0:
            failures.append(f"{archetype_id}_unknown_content_bearing_layer")
        if int(report.get("duplicate_bbox_collision_count", 0)) > 0:
            failures.append(f"{archetype_id}_duplicate_bbox_collision")
    dashboard = archetype_reports.get("data_dashboard", {})
    if (dashboard.get("native_component_report") or {}).get("native_chart_table_decision") != "passed":
        failures.append("data_dashboard_native_component_failed")
    table = archetype_reports.get("table_heavy", {})
    if (table.get("native_component_report") or {}).get("native_chart_table_decision") != "passed":
        failures.append("table_heavy_native_component_failed")
    return {
        "schema_name": "e02_generalization_gate",
        "status": "passed" if not failures else "failed",
        "decision": "E02_GENERALIZATION_PASS" if not failures else "E02_GENERALIZATION_PATCH_REQUIRED",
        "failures": sorted(set(failures)),
        "layout_signatures": dict((key, value.get("layout_signature")) for key, value in archetype_reports.items()),
        "canva_parity_claimed": False,
    }
