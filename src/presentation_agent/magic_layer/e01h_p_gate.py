"""Strict E01H-P Canva+ hybrid gate with icon and micro-component checks."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e01h_canva_plus_hybrid_gate import build_canva_plus_hybrid_gate_report


def build_patched_canva_plus_hybrid_gate_report(
    *,
    candidate_exists: bool,
    candidate_rendered: bool,
    visual_richness: dict[str, Any],
    payload: dict[str, Any],
    semantic_reports: dict[str, dict[str, Any]],
    icon_report: dict[str, Any],
    micro_component_report: dict[str, Any],
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    base = build_canva_plus_hybrid_gate_report(
        candidate_exists=candidate_exists,
        candidate_rendered=candidate_rendered,
        visual_richness=visual_richness,
        payload=payload,
        semantic_reports=semantic_reports,
        protected_artifacts_unchanged=protected_artifacts_unchanged,
    )
    strict_checks = {
        **base["checks"],
        "semantic_icon_vector_fidelity_passes": icon_report["status"] == "passed",
        "semantic_icon_vector_coverage_threshold": icon_report["semantic_icon_vector_coverage"] >= 0.9,
        "required_semantic_icon_missing_count_zero": icon_report.get("semantic_icon_missing_count", icon_report.get("required_semantic_icon_missing_count", 0)) == 0,
        "semantic_icon_raster_violation_count_zero": icon_report["semantic_icon_raster_violation_count"] == 0,
        "empty_circle_placeholder_not_accepted": icon_report.get("empty_circle_placeholder_accepted_count", 0) == 0 and icon_report.get("empty_circle_placeholder_count", 0) == 0,
        "micro_component_fidelity_passes": micro_component_report["status"] == "passed",
    }
    passed = all(strict_checks.values())
    return {
        "schema_name": "patched_canva_plus_hybrid_gate_report",
        "status": "passed" if passed else "failed",
        "decision": "single_reference_canva_plus_hybrid_icon_microcomponent_pass" if passed else "single_reference_canva_plus_hybrid_icon_microcomponent_patch_required",
        "checks": strict_checks,
        "single_reference_canva_plus_hybrid_pass": passed,
        "single_reference_e01h_p_pass": passed,
        "broad_canva_parity_claimed": False,
        "canva_parity_claimed": False,
    }


def build_e02h_readiness_after_e01h_p(gate_report: dict[str, Any], icon_report: dict[str, Any], semantic_reports: dict[str, dict[str, Any]], unknown_report: dict[str, Any]) -> dict[str, Any]:
    passed = (
        gate_report["status"] == "passed"
        and icon_report["semantic_icon_vector_coverage"] >= 0.9
        and icon_report.get("semantic_icon_missing_count", icon_report.get("required_semantic_icon_missing_count", 0)) == 0
        and semantic_reports["semantic_raster_violation_report"]["semantic_raster_violation_count"] == 0
        and unknown_report["unknown_content_bearing_layer_count"] == 0
    )
    return {
        "schema_name": "e02h_readiness_after_e01h_p",
        "status": "passed" if passed else "failed",
        "decision": "E01H_P_PASS_START_E02H_4CORE_HYBRID_CANVA_PLUS" if passed else _patch_decision(icon_report, gate_report),
        "e02h_unlocked": passed,
        "e05_unlocked": False,
        "e05_locked": True,
        "semantic_icon_vector_coverage": icon_report["semantic_icon_vector_coverage"],
        "required_semantic_icon_missing_count": icon_report.get("semantic_icon_missing_count", icon_report.get("required_semantic_icon_missing_count", 0)),
        "semantic_raster_violation_count": semantic_reports["semantic_raster_violation_report"]["semantic_raster_violation_count"],
        "unknown_content_bearing_layer_count": unknown_report["unknown_content_bearing_layer_count"],
        "reason": "E01H-P icon and micro-component fidelity passed; unlock E02H only." if passed else "E01H-P strict icon or micro-component gate did not pass.",
        "canva_parity_claimed": False,
    }


def patched_canva_plus_hybrid_gate_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Patched Canva+ Hybrid Gate Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Decision: `{report['decision']}`",
        "- Broad Canva parity claimed: `False`",
        "",
        "## Checks",
    ]
    for key, value in report["checks"].items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines)


def e02h_readiness_after_e01h_p_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# E02H Readiness After E01H-P",
            "",
            f"- Status: `{report['status']}`",
            f"- Decision: `{report['decision']}`",
            f"- E02H unlocked: `{report['e02h_unlocked']}`",
            f"- E05 unlocked: `{report['e05_unlocked']}`",
            f"- Semantic icon vector coverage: `{report['semantic_icon_vector_coverage']}`",
            f"- Required semantic icon missing count: `{report['required_semantic_icon_missing_count']}`",
            f"- Semantic raster violations: `{report['semantic_raster_violation_count']}`",
            f"- Unknown content-bearing layers: `{report['unknown_content_bearing_layer_count']}`",
            "- Broad Canva parity claimed: `False`",
        ]
    )


def _patch_decision(icon_report: dict[str, Any], gate_report: dict[str, Any]) -> str:
    if icon_report["semantic_icon_raster_violation_count"] > 0:
        return "E01H_P_FAIL_SEMANTIC_ICON_EDITABILITY"
    if icon_report.get("semantic_icon_missing_count", icon_report.get("required_semantic_icon_missing_count", 0)) > 0:
        return "E01H_P_PATCH_ICON_VECTORIZATION"
    if icon_report["semantic_icon_vector_coverage"] < 0.9:
        return "E01H_P_PATCH_ICON_VECTORIZATION"
    if not gate_report["checks"].get("micro_component_fidelity_passes", False):
        return "E01H_P_PATCH_MICRO_COMPONENT_FIDELITY"
    return "E01H_P_PATCH_RENDER_FIDELITY"
