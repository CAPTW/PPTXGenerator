"""Per-reference Canva+ hybrid gate for E03H."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e02h_canva_plus_hybrid_gate import (
    build_e02h_canva_plus_hybrid_gate_report,
    build_e02h_semantic_editability_reports,
    canva_plus_hybrid_gate_report_markdown,
)


def build_e03h_semantic_editability_reports(payload: dict[str, Any], inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    reports = build_e02h_semantic_editability_reports(payload, inventory)
    reference_id = payload["reference_id"]
    if reference_id == "comparison_matrix_hybrid":
        passed = inventory.get("native_table_count", 0) >= 1
        reports["semantic_table_editability_report"].update(
            {
                "status": "passed" if passed else "failed",
                "table_status": "native_table" if passed else "failed_missing_native_table",
                "native_table_count": inventory.get("native_table_count", 0),
            }
        )
    return reports


def build_e03h_canva_plus_hybrid_gate_report(
    *,
    reference_id: str,
    candidate_exists: bool,
    candidate_rendered: bool,
    visual_richness: dict[str, Any],
    payload: dict[str, Any],
    semantic_reports: dict[str, dict[str, Any]],
    icon_report: dict[str, Any],
    micro_component_report: dict[str, Any],
    component_gate: dict[str, Any],
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    report = build_e02h_canva_plus_hybrid_gate_report(
        reference_id=reference_id,
        candidate_exists=candidate_exists,
        candidate_rendered=candidate_rendered,
        visual_richness=visual_richness,
        payload=payload,
        semantic_reports=semantic_reports,
        icon_report=icon_report,
        micro_component_report=micro_component_report,
        component_gate=component_gate,
        protected_artifacts_unchanged=protected_artifacts_unchanged,
    )
    report["schema_name"] = "canva_plus_hybrid_gate_report"
    report["gate_scope"] = "e03h_reference_pack_per_reference"
    report["decision"] = "e03h_reference_canva_plus_hybrid_pass" if report["status"] == "passed" else "e03h_reference_canva_plus_hybrid_patch_required"
    report["e05_unlocked"] = False
    return report


def build_e05_readiness_after_e03h(gate_or_aggregate_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e05_readiness_after_e03h",
        "status": "blocked",
        "e05_unlocked": False,
        "e05_locked": True,
        "reason": "E03H may unlock E04H only; E05 requires later E04H source-bound validation.",
        "e04h_unlocked": gate_or_aggregate_report.get("e04h_unlocked", False),
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "canva_parity_claimed": False,
    }


def e05_readiness_after_e03h_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# E05 Readiness After E03H",
            "",
            f"- Status: `{report['status']}`",
            f"- E05 unlocked: `{report['e05_unlocked']}`",
            f"- E05 locked: `{report['e05_locked']}`",
            f"- Reason: {report['reason']}",
            "- Broad Canva parity claimed: `False`",
        ]
    )


__all__ = [
    "build_e03h_semantic_editability_reports",
    "build_e03h_canva_plus_hybrid_gate_report",
    "build_e05_readiness_after_e03h",
    "canva_plus_hybrid_gate_report_markdown",
    "e05_readiness_after_e03h_markdown",
]
