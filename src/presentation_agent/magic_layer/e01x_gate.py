"""E01X integration gate evaluation."""

from __future__ import annotations

from typing import Any


def evaluate_e01x_gate(candidate: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    risks: list[str] = list(candidate.get("high_product_risks") or [])
    checks = {
        "editable_candidate_exists": "editable_candidate_missing",
        "candidate_rendered": "candidate_render_missing",
        "ps_layer_protocol_valid": "ps_layer_protocol_invalid",
        "e01p_v_precompile_passed": "e01p_v_precompile_failed",
        "e01p_v_postcompile_passed": "e01p_v_postcompile_failed",
        "semantic_text_editable": "semantic_text_not_editable",
        "semantic_icons_vector_or_absent": "semantic_icons_not_vector",
        "semantic_chart_table_editable_or_absent": "semantic_chart_table_not_editable",
        "cards_panels_footer_native": "cards_panels_footer_not_native",
        "smart_objects_replaceable": "smart_objects_not_replaceable",
    }
    for key, code in checks.items():
        if candidate.get(key) is not True:
            failures.append(code)
    if candidate.get("full_slide_reference_background") is True:
        failures.append("full_slide_reference_background_forbidden")
    if candidate.get("screenshot_slide") is True:
        failures.append("screenshot_slide_forbidden")
    if int(candidate.get("object_graph_node_count", 0)) < 8:
        failures.append("object_graph_not_nontrivial")
    if int(candidate.get("unknown_content_bearing_layer_count", 0)) > 0:
        failures.append("unknown_content_bearing_layer")
    if int(candidate.get("semantic_raster_violation_count", 0)) > 0:
        failures.append("semantic_raster_violation")
    if candidate.get("reference_vs_render_fidelity") not in {"acceptable", "pass", "strong"}:
        risks.append("reference_vs_render_not_acceptable")
    failures.extend(candidate.get("critical_blockers") or [])
    status = "passed" if not failures and not risks else "failed"
    return {
        "schema_name": "canva_plus_gate_report",
        "status": status,
        "decision": "E01X_CANVA_PLUS_STRUCTURAL_PASS" if status == "passed" else "E01X_CANVA_PLUS_PATCH_REQUIRED",
        "failures": failures,
        "high_product_risks": risks,
        "e02_unlocked": False,
        "canva_parity_claimed": False,
        "candidate": candidate,
    }


def final_decision_for_gate(gate: dict[str, Any], *, protected_artifacts_unchanged: bool) -> dict[str, Any]:
    if not protected_artifacts_unchanged:
        decision = "E01X_FAIL_PROTECTED_ARTIFACTS"
    elif gate.get("status") == "passed":
        decision = "E01X_PASS_READY_FOR_E02_4CORE_WITH_PS_LAYER"
    elif any(code in gate.get("failures", []) for code in ("semantic_text_not_editable", "semantic_icons_not_vector", "semantic_chart_table_not_editable", "semantic_raster_violation")):
        decision = "E01X_FAIL_SEMANTIC_EDITABILITY"
    elif any(code.startswith("ps_layer") or "e01p_v" in code for code in gate.get("failures", [])):
        decision = "E01X_FAIL_PS_LAYER_VALIDATION"
    elif "reference_vs_render_not_acceptable" in gate.get("high_product_risks", []):
        decision = "E01X_PATCH_RENDER_FIDELITY"
    else:
        decision = "E01X_PATCH_PPTX_COMPILER"
    return {
        "schema_name": "e01x_final_decision",
        "status": "passed" if decision == "E01X_PASS_READY_FOR_E02_4CORE_WITH_PS_LAYER" else "failed",
        "decision": decision,
        "e02_unlocked": decision == "E01X_PASS_READY_FOR_E02_4CORE_WITH_PS_LAYER" and protected_artifacts_unchanged,
        "e02_started": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "protected_artifacts_unchanged": protected_artifacts_unchanged,
        "canva_parity_claimed": False,
    }
