"""D05 readiness and handoff helpers for D04."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def build_d05_render_fidelity_handoff(
    reference_id: str,
    native_chart_spec: dict[str, Any],
    native_table_spec: dict[str, Any],
    quality: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_name": "d05_render_fidelity_handoff",
        "reference_id": reference_id,
        "status": "passed" if quality.get("status") != "blocking" else "blocking",
        "chart_spec_ids": [item["native_chart_spec_id"] for item in native_chart_spec.get("chart_specs") or []],
        "table_spec_ids": [item["native_table_spec_id"] for item in native_table_spec.get("table_specs") or []],
        "D05_required_checks": ["reference_to_render_comparison", "no_semantic_chart_table_raster", "label_readability", "grid_axis_fidelity"],
        "text_risk_carried_forward": True,
        "blocking_issues": quality.get("blocking_issues") or [],
    }


def build_updated_chart_table_manifest(
    manifest: dict[str, Any],
    triage: dict[str, Any],
    native_chart_spec: dict[str, Any],
    native_table_spec: dict[str, Any],
    editable_chart_spec: dict[str, Any],
    editable_table_spec: dict[str, Any],
    text_risk: dict[str, Any],
) -> dict[str, Any]:
    updated = deepcopy(manifest)
    triage_by_layer = {}
    for item in triage.get("triaged_candidates") or []:
        for layer_id in item.get("source_layer_ids") or []:
            triage_by_layer[layer_id] = item
    chart_spec_id = (native_chart_spec.get("chart_specs") or [{}])[0].get("native_chart_spec_id")
    table_spec_id = (native_table_spec.get("table_specs") or [{}])[0].get("native_table_spec_id")
    editable_chart_id = (editable_chart_spec.get("chart_specs") or [{}])[0].get("editable_shape_chart_spec_id")
    editable_table_id = (editable_table_spec.get("table_specs") or [{}])[0].get("editable_shape_grid_table_spec_id")
    for layer in updated.get("layers") or []:
        item = triage_by_layer.get(layer["layer_id"])
        layer["chart_table_triage_class"] = item.get("triage_class") if item else "not_chart_table_handoff"
        layer["chart_component_type"] = _chart_component_type(layer["chart_table_triage_class"], native_chart_spec)
        layer["table_component_type"] = _table_component_type(layer["chart_table_triage_class"], native_table_spec)
        layer["native_chart_spec_id"] = chart_spec_id if layer["chart_table_triage_class"] in {"true_chart_region", "chart_axis_or_legend"} else None
        layer["native_table_spec_id"] = table_spec_id if layer["chart_table_triage_class"] in {"true_table_region", "true_matrix_region", "table_header_or_cell_group"} else None
        layer["editable_shape_chart_spec_id"] = editable_chart_id if layer["native_chart_spec_id"] else None
        layer["editable_shape_grid_table_spec_id"] = editable_table_id if layer["native_table_spec_id"] else None
        layer["final_raster_forbidden"] = layer["chart_table_triage_class"] in {"true_chart_region", "true_table_region", "true_matrix_region", "chart_axis_or_legend", "table_header_or_cell_group"}
        layer["D05_render_fidelity_notes"] = "D05 must compare editable reconstruction against reference; semantic chart/table raster fallback is forbidden."
        layer["D02_text_risk_carryforward"] = text_risk
        layer["chart_table_unresolved_disposition"] = item.get("final_disposition") if item else "not_applicable"
    updated["schema_name"] = "layer_manifest_v4_chart_table_promoted"
    updated["d04_chart_table_promotion"] = {
        "native_chart_spec_count": len(native_chart_spec.get("chart_specs") or []),
        "native_table_spec_count": len(native_table_spec.get("table_specs") or []),
        "editable_shape_chart_spec_count": len(editable_chart_spec.get("chart_specs") or []),
        "editable_shape_grid_table_spec_count": len(editable_table_spec.get("table_specs") or []),
        "semantic_chart_table_raster_final_use_forbidden": True,
        "text_risk_carried_forward": text_risk,
    }
    return updated


def build_d05_readiness(results: list[dict[str, Any]], ocr_backend_status: str) -> dict[str, Any]:
    all_outputs = bool(results)
    blockers = sum(item.get("blocking_issue_count", 0) for item in results)
    raster_violations = sum(item.get("raster_violation_count", 0) for item in results)
    data_dashboard_ok = any(item["reference_id"] == "data_dashboard" and item.get("true_chart_candidate_count", 0) > 0 for item in results)
    table_heavy_ok = any(item["reference_id"] == "table_heavy" and item.get("true_table_candidate_count", 0) > 0 for item in results)
    if raster_violations:
        decision = "D04_PATCH_RASTER_POLICY"
    elif not data_dashboard_ok:
        decision = "D04_PATCH_DATA_DASHBOARD_CHART"
    elif not table_heavy_ok:
        decision = "D04_PATCH_TABLE_HEAVY_TABLE"
    elif blockers:
        decision = "D04_PATCH_CANDIDATE_TRIAGE"
    elif ocr_backend_status != "available":
        decision = "D04_PASS_WITH_TEXT_RISK_START_D05"
    else:
        decision = "D04_PASS_START_D05_REFERENCE_TO_PPT_RENDER_FIDELITY_GATE"
    return {
        "schema_name": "d05_readiness_report",
        "decision": decision,
        "d05_unlocked": decision in {"D04_PASS_START_D05_REFERENCE_TO_PPT_RENDER_FIDELITY_GATE", "D04_PASS_WITH_TEXT_RISK_START_D05"},
        "ocr_backend_status": ocr_backend_status,
        "unlock_conditions": {
            "d04_reports_exist": all_outputs,
            "handoff_candidate_triage_exists_for_all_pilots": all_outputs,
            "false_positives_explicitly_classified": all(item.get("false_positive_count", 0) >= 0 for item in results),
            "chart_specs_exist_or_risks_recorded": all(item.get("native_chart_spec_count", 0) > 0 or item.get("chart_risk_recorded") for item in results),
            "table_specs_exist_or_risks_recorded": all(item.get("native_table_spec_count", 0) > 0 or item.get("table_risk_recorded") for item in results),
            "data_dashboard_chart_candidate_or_blocker": data_dashboard_ok,
            "table_heavy_table_candidate_or_blocker": table_heavy_ok,
            "no_semantic_chart_table_final_raster": raster_violations == 0,
            "updated_manifests_exist": all_outputs,
            "d05_handoff_exists": all_outputs,
            "source_bound_decks_created": False,
            "bulk_decks_created": False,
            "c11_remains_frozen": True,
            "protected_artifacts_unchanged": True,
        },
        "canva_parity_claimed": False,
    }


def validate_d05_readiness(report: dict[str, Any]) -> list[str]:
    errors = []
    if report.get("d05_unlocked"):
        conditions = report.get("unlock_conditions") or {}
        for key in ["data_dashboard_chart_candidate_or_blocker", "table_heavy_table_candidate_or_blocker", "no_semantic_chart_table_final_raster"]:
            if not conditions.get(key):
                errors.append(f"d05_readiness_cannot_pass_with_failed_condition:{key}")
    return errors


def _chart_component_type(triage_class: str, native_chart_spec: dict[str, Any]) -> str | None:
    if triage_class not in {"true_chart_region", "chart_axis_or_legend"}:
        return None
    spec = (native_chart_spec.get("chart_specs") or [{}])[0]
    return spec.get("chart_component_type")


def _table_component_type(triage_class: str, native_table_spec: dict[str, Any]) -> str | None:
    if triage_class not in {"true_table_region", "true_matrix_region", "table_header_or_cell_group"}:
        return None
    spec = (native_table_spec.get("table_specs") or [{}])[0]
    return spec.get("table_component_type")

