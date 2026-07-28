"""E03 template-pack pass/fail gate."""

from __future__ import annotations

from typing import Any


def evaluate_e03_pack_gate(
    *,
    archetype_reports: dict[str, dict[str, Any]],
    required_core_ids: list[str],
    pack_artifacts: dict[str, bool],
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    failures: list[str] = []
    for archetype_id in required_core_ids:
        report = archetype_reports.get(archetype_id)
        if report is None:
            failures.append(f"{archetype_id}_missing")
            continue
        if report.get("status") != "passed":
            failures.append(f"{archetype_id}_failed")
        if report.get("e01p_v_postcompile_status") != "passed":
            failures.append(f"{archetype_id}_e01p_v_postcompile_failed")
        if report.get("visual_slot_fidelity_status") != "passed":
            failures.append(f"{archetype_id}_visual_slot_fidelity_failed")
        if int(report.get("semantic_raster_violation_count", 0)) > 0:
            failures.append(f"{archetype_id}_semantic_raster_violation")
        if int(report.get("unknown_content_bearing_count", 0)) > 0:
            failures.append(f"{archetype_id}_unknown_content_bearing")
        if int(report.get("duplicate_bbox_collision_count", 0)) > 0:
            failures.append(f"{archetype_id}_duplicate_bbox_collision")
    for archetype_id, code in {
        "data_dashboard": "data_dashboard_native_chart_failed",
        "table_heavy": "table_heavy_native_table_failed",
        "comparison_matrix": "comparison_matrix_native_table_failed",
    }.items():
        if archetype_id in archetype_reports and archetype_reports[archetype_id].get("native_chart_table_decision") != "passed":
            failures.append(code)
    for artifact, exists in pack_artifacts.items():
        if not exists:
            failures.append(f"missing_pack_artifact:{artifact}")
    if not protected_artifacts_unchanged:
        failures.append("protected_artifacts_changed")
    return {
        "schema_name": "e03_pack_gate",
        "status": "passed" if not failures else "failed",
        "decision": "E03_PACK_PASS" if not failures else "E03_PACK_PATCH_REQUIRED",
        "failures": sorted(set(failures)),
        "canva_parity_claimed": False,
    }
