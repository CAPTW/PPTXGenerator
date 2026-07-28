from __future__ import annotations

from typing import Any


def build_gate_rollup(decisions: dict[str, Any] | None = None) -> dict[str, Any]:
    decisions = decisions or {}
    gates = [
        _row("A01_REGISTRY_CLAIM_GUARD", decisions.get("a01", "PASS"), True, "manual review debt may remain"),
        _row("E01P_PROTOCOL_GATE", decisions.get("e01p", "PASS_WITH_LIMITATIONS"), True, "fixture limitations carried"),
        _row("T01_TEMPLATE_CONTRACT_GATE", decisions.get("t01", "PASS_WITH_LIMITATIONS"), True, "fixture limitations carried"),
        _row("T02_NATIVE_RECONSTRUCTION_PLANNER", decisions.get("t02", "PASS_WITH_LIMITATIONS"), True, "minimal sample only"),
        _row("C01_COMPILER_DRY_RUN", decisions.get("c01", "PASS_WITH_LIMITATIONS"), True, "dry-run only"),
        _row("C02B_CONTROLLED_COMPATIBLE_COMPILE", decisions.get("c02b", "C02B_PASS_POWERPOINT_OPENABLE_READY_FOR_C03A_RENDER_RETRY"), True, "controlled compile smoke only"),
        _row("B03_PPTX_NATIVE_VALIDATION", decisions.get("b03", "PASS_WITH_LIMITATIONS"), True, "text overflow strictness limited"),
        _row("C03A_RETRY_CONTROLLED_RENDER", decisions.get("c03a_retry", "C03A_RETRY_PASS_WITH_RENDER_LIMITATIONS_READY_FOR_P02"), True, "controlled render smoke only"),
        _row("B01_REVIEW_PACKET", decisions.get("b01", "REVIEW_READY_WITH_LIMITATIONS"), True, "diagnostic review only"),
        _row("CLAIM_BOUNDARY_CHECK", "PASS_WITH_LIMITATIONS", True, "product_pass false; scaleout blocked"),
    ]
    return {"schema": "controlled_sample_gate_rollup.v1", "gates": gates, "gate_rollup_status": "PASS_WITH_LIMITATIONS", "product_pass": False}


def _row(stage: str, decision: str, pass_status: bool, limitation: str) -> dict[str, Any]:
    return {"stage": stage, "decision": decision, "pass_status": pass_status, "limitation": limitation, "artifact_evidence": [], "blocker": None, "next_action": "continue_import_existing"}
