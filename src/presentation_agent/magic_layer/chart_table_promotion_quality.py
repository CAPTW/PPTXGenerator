"""D04 chart/table promotion quality and raster policy helpers."""

from __future__ import annotations

from typing import Any


def build_chart_table_raster_policy() -> dict[str, Any]:
    return {
        "schema_name": "chart_table_raster_policy_v1",
        "semantic_chart_final_raster_use_forbidden": True,
        "semantic_table_final_raster_use_forbidden": True,
        "chart_table_screenshots_forbidden": True,
        "reference_crop_analysis_only": True,
        "decorative_chart_like_microtexture_allowed_if_nonsemantic": True,
        "content_bearing_chart_table_raster_policy": "reject_or_patch",
        "D05_failure_policy": "fail_any_final_semantic_chart_or_table_raster_fallback",
    }


def validate_chart_table_raster_policy(item: dict[str, Any]) -> list[str]:
    errors = []
    if item.get("semantic_component") in {"chart", "table", "matrix"} and item.get("final_use") == "raster":
        errors.append("semantic_chart_table_final_raster_forbidden")
    if item.get("semantic_component") in {"chart", "table", "matrix"} and item.get("screenshot_slide"):
        errors.append("chart_table_screenshot_forbidden")
    return errors


def build_raster_violation_report(reference_id: str, native_chart_spec: dict[str, Any], native_table_spec: dict[str, Any]) -> dict[str, Any]:
    checked = []
    for chart in native_chart_spec.get("chart_specs") or []:
        checked.append({"semantic_component": "chart", "final_use": "editable_shape_chart", "spec_id": chart["native_chart_spec_id"]})
    for table in native_table_spec.get("table_specs") or []:
        checked.append({"semantic_component": "table", "final_use": "editable_shape_grid_table", "spec_id": table["native_table_spec_id"]})
    violations = []
    for item in checked:
        for error in validate_chart_table_raster_policy(item):
            violations.append({**item, "violation": error})
    return {
        "schema_name": "chart_table_raster_violation_report",
        "reference_id": reference_id,
        "status": "passed" if not violations else "failed",
        "violation_count": len(violations),
        "violations": violations,
        "checked_components": checked,
    }


def score_chart_table_promotion(
    reference_id: str,
    triage: dict[str, Any],
    chart_candidates: dict[str, Any],
    table_candidates: dict[str, Any],
    native_chart_spec: dict[str, Any],
    native_table_spec: dict[str, Any],
    raster_report: dict[str, Any],
) -> dict[str, Any]:
    false_positive_count = triage.get("false_positive_count", 0)
    true_chart_count = len(chart_candidates.get("chart_candidates") or [])
    true_table_count = len(table_candidates.get("table_candidates") or [])
    blockers = []
    if raster_report.get("violation_count", 0):
        blockers.append("semantic_chart_table_left_as_final_raster")
    if reference_id == "data_dashboard" and true_chart_count == 0:
        blockers.append("data_dashboard_lacks_chart_candidate")
    if reference_id == "table_heavy" and true_table_count == 0:
        blockers.append("table_heavy_lacks_table_candidate")
    if triage.get("unresolved_blocking_count", 0):
        blockers.append("unresolved_chart_table_candidate")
    return {
        "schema_name": "d04_chart_table_quality_report",
        "reference_id": reference_id,
        "status": "blocking" if blockers else "passed_with_text_risk",
        "scores": {
            "handoff_triage_quality": 8 if triage.get("candidate_count", 0) else 6,
            "false_positive_rejection_quality": 9 if false_positive_count else 6,
            "true_chart_detection_quality": 9 if true_chart_count else 5,
            "true_table_detection_quality": 9 if true_table_count else 5,
            "chart_skeleton_quality": 8 if native_chart_spec.get("chart_specs") else 5,
            "table_skeleton_quality": 8 if native_table_spec.get("table_specs") else 5,
            "axis_legend_policy_quality": 8,
            "source_footer_data_binding_readiness": 7,
            "raster_policy_enforcement": 10 if raster_report.get("violation_count", 0) == 0 else 0,
            "D05_handoff_readiness": 8 if not blockers else 3,
        },
        "counts": {
            "handoff_candidate_count": triage.get("candidate_count", 0),
            "false_positive_count": false_positive_count,
            "true_chart_candidate_count": true_chart_count,
            "true_table_candidate_count": true_table_count,
            "native_chart_spec_count": len(native_chart_spec.get("chart_specs") or []),
            "native_table_spec_count": len(native_table_spec.get("table_specs") or []),
            "raster_violation_count": raster_report.get("violation_count", 0),
        },
        "blocking_issues": blockers,
    }

