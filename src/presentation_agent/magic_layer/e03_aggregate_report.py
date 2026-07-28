"""E03 aggregate report and final decision classifier."""

from __future__ import annotations

from typing import Any


def build_e03_template_pack_report(
    *,
    archetype_reports: dict[str, dict[str, Any]],
    pack_gate: dict[str, Any],
    component_coverage_matrix: dict[str, Any],
    distinctiveness_report: dict[str, Any],
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    failures = []
    if pack_gate.get("status") != "passed":
        failures.extend(pack_gate.get("failures", []))
    if component_coverage_matrix.get("status") != "passed":
        failures.append("component_coverage_matrix_failed")
    if distinctiveness_report.get("status") != "passed":
        failures.append("archetype_distinctiveness_failed")
    if not protected_artifacts_unchanged:
        failures.append("protected_artifacts_changed")
    return {
        "schema_name": "e03_template_pack_report",
        "status": "passed" if not failures else "failed",
        "archetypes": archetype_reports,
        "pack_gate": pack_gate,
        "component_coverage_matrix_status": component_coverage_matrix.get("status"),
        "archetype_distinctiveness_status": distinctiveness_report.get("status"),
        "protected_artifacts_unchanged": protected_artifacts_unchanged,
        "failures": sorted(set(failures)),
        "integration_risk": "low" if not failures else "patch_required",
        "e04_readiness": "ready" if not failures else "blocked",
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "e04_started": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
    }


def final_decision_for_e03(report: dict[str, Any]) -> dict[str, Any]:
    failures = set(report.get("failures", []))
    if not report.get("protected_artifacts_unchanged"):
        decision = "E03_FAIL_PROTECTED_ARTIFACTS"
    elif report.get("status") == "passed":
        decision = "E03_PASS_READY_FOR_E04_SOURCE_BOUND_SMALL_DECK"
    elif "archetype_distinctiveness_failed" in failures:
        decision = "E03_FAIL_ARCHETYPE_DISTINCTIVENESS"
    elif any("native_chart" in failure for failure in failures):
        decision = "E03_PATCH_NATIVE_CHART_RECONSTRUCTION"
    elif any("native_table" in failure for failure in failures):
        decision = "E03_PATCH_NATIVE_TABLE_RECONSTRUCTION"
    elif any("visual_slot" in failure or "duplicate_bbox" in failure for failure in failures):
        decision = "E03_PATCH_VISUAL_SLOT_FIDELITY"
    elif any("semantic_raster" in failure or "unknown_content" in failure for failure in failures):
        decision = "E03_FAIL_SEMANTIC_EDITABILITY"
    elif any("e01p_v" in failure for failure in failures):
        decision = "E03_FAIL_PS_LAYER_VALIDATION"
    elif "component_coverage_matrix_failed" in failures:
        decision = "E03_PATCH_COMPONENT_LIBRARY"
    else:
        decision = "E03_PATCH_ARCHETYPE_CONTRACTS"
    return {
        "schema_name": "e03_final_decision",
        "status": "passed" if decision == "E03_PASS_READY_FOR_E04_SOURCE_BOUND_SMALL_DECK" else "failed",
        "decision": decision,
        "e04_unlocked": decision == "E03_PASS_READY_FOR_E04_SOURCE_BOUND_SMALL_DECK",
        "e04_started": False,
        "e05_started": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
    }
