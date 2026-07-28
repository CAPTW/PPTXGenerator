"""Aggregate E02 reports and classify the final gate decision."""

from __future__ import annotations

from typing import Any


def build_e02_aggregate_report(archetypes: dict[str, dict[str, Any]], generalization_gate: dict[str, Any], *, protected_artifacts_unchanged: bool) -> dict[str, Any]:
    failures = []
    for archetype_id, report in archetypes.items():
        if report.get("status") != "passed":
            failures.append(f"{archetype_id}_failed")
    if generalization_gate.get("status") != "passed":
        failures.extend(generalization_gate.get("failures", []))
    if not protected_artifacts_unchanged:
        failures.append("protected_artifacts_changed")
    return {
        "schema_name": "e02_4core_conversion_report",
        "status": "passed" if not failures else "failed",
        "archetypes": archetypes,
        "generalization_gate": generalization_gate,
        "protected_artifacts_unchanged": protected_artifacts_unchanged,
        "failures": sorted(set(failures)),
        "integration_risk": "low" if not failures else "patch_required",
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "e03_started": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
    }


def final_decision_for_e02(report: dict[str, Any]) -> dict[str, Any]:
    decision = "E02_PASS_READY_FOR_E03_12_16_ARCHETYPE_PACK"
    if not report.get("protected_artifacts_unchanged"):
        decision = "E02_FAIL_PROTECTED_ARTIFACTS"
    elif report.get("status") != "passed":
        failures = set(report.get("failures", []))
        archetypes = report.get("archetypes", {})
        if any("semantic_raster" in failure or "unknown_content" in failure for failure in failures):
            decision = "E02_FAIL_SEMANTIC_EDITABILITY"
        elif any("e01p_v" in failure for failure in failures):
            decision = "E02_FAIL_PS_LAYER_VALIDATION"
        elif "data_dashboard_native_component_failed" in failures or (archetypes.get("data_dashboard", {}).get("native_chart_table_decision") == "failed"):
            decision = "E02_PATCH_CHART_RECONSTRUCTION"
        elif "table_heavy_native_component_failed" in failures or (archetypes.get("table_heavy", {}).get("native_chart_table_decision") == "failed"):
            decision = "E02_PATCH_TABLE_RECONSTRUCTION"
        elif any("duplicate_bbox" in failure or "visual_slot" in failure for failure in failures):
            decision = "E02_PATCH_VISUAL_SLOT_FIDELITY"
        elif any("layout_signature" in failure or "same_layout" in failure for failure in failures):
            decision = "E02_FAIL_GENERALIZATION"
        elif "cover_hero_failed" in failures:
            decision = "E02_PATCH_COVER_HERO"
        elif "standard_content_failed" in failures:
            decision = "E02_PATCH_STANDARD_CONTENT"
        elif "data_dashboard_failed" in failures:
            decision = "E02_PATCH_DATA_DASHBOARD"
        elif "table_heavy_failed" in failures:
            decision = "E02_PATCH_TABLE_HEAVY"
        else:
            decision = "E02_PARTIAL_PASS_PATCH_COMPONENTS"
    return {
        "schema_name": "e02_final_decision",
        "status": "passed" if decision == "E02_PASS_READY_FOR_E03_12_16_ARCHETYPE_PACK" else "failed",
        "decision": decision,
        "e03_unlocked": decision == "E02_PASS_READY_FOR_E03_12_16_ARCHETYPE_PACK",
        "e03_started": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
    }
