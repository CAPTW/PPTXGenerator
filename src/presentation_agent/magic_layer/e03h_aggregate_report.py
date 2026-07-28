"""Aggregate reports for the E03H 12-core hybrid reference pack gate."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e03h_reference_registry import CORE_REFERENCE_IDS


CORE_REFERENCE_SET = set(CORE_REFERENCE_IDS)


def build_e03h_aggregate_report(
    per_reference: dict[str, dict[str, Any]],
    *,
    pack_report: dict[str, Any],
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    failures: list[str] = []
    missing_core = [reference_id for reference_id in CORE_REFERENCE_IDS if reference_id not in per_reference]
    if missing_core:
        failures.append("missing_core_references")
    for reference_id, report in per_reference.items():
        if report.get("core", reference_id in CORE_REFERENCE_SET) and report.get("status") != "passed":
            failures.append(f"{reference_id}_gate_failed")
        if report.get("semantic_raster_violation_count", 1) != 0:
            failures.append(f"{reference_id}_semantic_raster_violation")
        if report.get("unknown_content_bearing_layer_count", 1) != 0:
            failures.append(f"{reference_id}_unknown_content_bearing")
        if report.get("full_slide_raster_count", 1) != 0:
            failures.append(f"{reference_id}_full_slide_raster")
        if report.get("screenshot_slide_count", 1) != 0:
            failures.append(f"{reference_id}_screenshot_slide")
        if report.get("visual_richness_status") != "passed":
            failures.append(f"{reference_id}_visual_richness_failed")
        if report.get("component_gate_status") != "passed":
            failures.append(f"{reference_id}_component_gate_failed")
    for reference_id in ("data_dashboard_hybrid", "table_matrix_hybrid", "comparison_matrix_hybrid"):
        if per_reference.get(reference_id, {}).get("native_chart_table_decision") != "passed":
            failures.append(f"{reference_id}_native_chart_table_failed")
    for reference_id in ("maritime_checklist_hero", "process_workflow_infographic", "data_dashboard_hybrid", "table_matrix_hybrid"):
        if per_reference.get(reference_id, {}).get("status") != "passed":
            failures.append(f"{reference_id}_e02h_regression")
    if pack_report.get("status") != "passed" or not pack_report.get("pptx_exists", bool(pack_report.get("pptx_path"))):
        failures.append("editable_hybrid_reference_pack_missing_or_failed")
    if not protected_artifacts_unchanged:
        failures.append("protected_artifacts_changed")
    passed = not failures
    return {
        "schema_name": "e03h_reference_pack_report",
        "status": "passed" if passed else "failed",
        "decision": "E03H_PASS_READY_FOR_E04H_SOURCE_BOUND_SMALL_DECK_WITH_HYBRID_PACK" if passed else _patch_decision(failures),
        "reference_count": len(per_reference),
        "core_reference_count": sum(1 for row in per_reference.values() if row.get("core", True)),
        "optional_reference_count": sum(1 for row in per_reference.values() if not row.get("core", True)),
        "per_reference": per_reference,
        "pack_report": pack_report,
        "semantic_raster_violation_count": sum(report.get("semantic_raster_violation_count", 0) for report in per_reference.values()),
        "unknown_content_bearing_layer_count": sum(report.get("unknown_content_bearing_layer_count", 0) for report in per_reference.values()),
        "full_slide_raster_count": sum(report.get("full_slide_raster_count", 0) for report in per_reference.values()),
        "screenshot_slide_count": sum(report.get("screenshot_slide_count", 0) for report in per_reference.values()),
        "protected_artifacts_unchanged": protected_artifacts_unchanged,
        "failures": failures,
        "e04h_unlocked": passed,
        "e05_unlocked": False,
        "e05_locked": True,
        "canva_parity_claimed": False,
    }


def build_e04h_readiness_report(aggregate_report: dict[str, Any]) -> dict[str, Any]:
    passed = aggregate_report["decision"] == "E03H_PASS_READY_FOR_E04H_SOURCE_BOUND_SMALL_DECK_WITH_HYBRID_PACK"
    return {
        "schema_name": "e04h_readiness_report",
        "status": "passed" if passed else "failed",
        "decision": aggregate_report["decision"],
        "e04h_unlocked": passed,
        "e05_unlocked": False,
        "e05_locked": True,
        "reason": "E03H passed; unlock E04H only." if passed else "E03H did not pass all core hybrid reference pack gates.",
        "canva_parity_claimed": False,
    }


def build_e03h_visual_richness_retention_matrix(reference_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = {
        reference_id: {
            "status": report.get("visual_richness_status"),
            "composition_similarity_score": report.get("composition_similarity_score"),
            "visual_backplates": report.get("visual_backplate_count"),
        }
        for reference_id, report in reference_reports.items()
    }
    return {
        "schema_name": "e03h_visual_richness_retention_matrix",
        "status": "passed" if rows and all(row["status"] == "passed" for row in rows.values()) else "failed",
        "references": rows,
        "canva_parity_claimed": False,
    }


def build_e03h_semantic_native_promotion_matrix(reference_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = {
        reference_id: {
            "native_chart_count": report.get("native_chart_count", 0),
            "native_table_count": report.get("native_table_count", 0),
            "semantic_raster_violation_count": report.get("semantic_raster_violation_count", 0),
            "native_chart_table_decision": report.get("native_chart_table_decision", "not_applicable"),
        }
        for reference_id, report in reference_reports.items()
    }
    passed = all(row["semantic_raster_violation_count"] == 0 for row in rows.values())
    return {"schema_name": "e03h_semantic_native_promotion_matrix", "status": "passed" if passed else "failed", "references": rows, "canva_parity_claimed": False}


def e03h_reference_pack_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# E03H Hybrid Reference Pack Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Decision: `{report['decision']}`",
        f"- E04H unlocked: `{report['e04h_unlocked']}`",
        f"- E05 unlocked: `{report['e05_unlocked']}`",
        "- Broad Canva parity claimed: `False`",
        "",
    ]
    for reference_id, row in report["per_reference"].items():
        lines.append(f"## {reference_id}")
        lines.append(f"- Status: `{row['status']}`")
        lines.append(f"- Component gate: `{row['component_gate_status']}`")
        lines.append(f"- Visual richness: `{row['visual_richness_status']}`")
    return "\n".join(lines)


def e04h_readiness_report_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# E04H Readiness Report",
            "",
            f"- Status: `{report['status']}`",
            f"- E04H unlocked: `{report['e04h_unlocked']}`",
            f"- E05 unlocked: `{report['e05_unlocked']}`",
            f"- Reason: {report['reason']}",
            "- Broad Canva parity claimed: `False`",
        ]
    )


def simple_matrix_markdown(title: str, report: dict[str, Any]) -> str:
    lines = [f"# {title}", "", f"- Status: `{report.get('status', 'n/a')}`", "- Broad Canva parity claimed: `False`", ""]
    for reference_id, row in report.get("references", report.get("coverage", {})).items():
        lines.append(f"## {reference_id}")
        for key, value in row.items():
            lines.append(f"- {key}: `{value}`")
    return "\n".join(lines)


def _patch_decision(failures: list[str]) -> str:
    if "protected_artifacts_changed" in failures:
        return "E03H_FAIL_PROTECTED_ARTIFACTS"
    if any("semantic_raster" in failure for failure in failures):
        return "E03H_FAIL_SEMANTIC_EDITABILITY"
    if any("data_dashboard" in failure for failure in failures):
        return "E03H_PATCH_DATA_DASHBOARD_CHART"
    if any("table_matrix" in failure or "comparison_matrix" in failure for failure in failures):
        return "E03H_PATCH_TABLE_MATRIX"
    if any("process_workflow" in failure for failure in failures):
        return "E03H_PATCH_PROCESS_WORKFLOW"
    if any("maritime" in failure for failure in failures):
        return "E03H_PATCH_MARITIME_CHECKLIST_REGRESSION"
    if any("visual_richness" in failure or "pack" in failure for failure in failures):
        return "E03H_PATCH_RENDER_FIDELITY"
    return "E03H_PATCH_VISUAL_BACKPLATE_POLICY"
