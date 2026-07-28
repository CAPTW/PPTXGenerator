from __future__ import annotations

from typing import Any


def build_gate_contract() -> dict[str, Any]:
    gates = [
        _gate("A01_REGISTRY_CLAIM_GUARD", "GOVERNANCE_GATE", ["PASS", "PASS_WITH_MANUAL_REVIEW_DEBT"]),
        _gate("E01P_PROTOCOL_GATE", "PRECOMPILE_PROTOCOL_GATE", ["PASS", "PASS_WITH_FIXTURE_LIMITATIONS"]),
        _gate("T01_TEMPLATE_CONTRACT_GATE", "CONTRACT_GATE", ["PASS", "PASS_WITH_FIXTURE_LIMITATIONS"]),
        _gate("T02_NATIVE_RECONSTRUCTION_PLANNER", "PLANNER_GATE", ["PASS", "PASS_WITH_FIXTURE_LIMITATIONS"]),
        _gate("C01_COMPILER_DRY_RUN", "DRY_RUN_GATE", ["DRY_RUN_READY", "PASS_WITH_FIXTURE_LIMITATIONS"]),
        _gate("C02B_CONTROLLED_COMPATIBLE_COMPILE", "COMPILE_SMOKE_GATE", ["C02B_PASS_POWERPOINT_OPENABLE_READY_FOR_C03A_RENDER_RETRY"]),
        _gate("B03_PPTX_NATIVE_VALIDATION", "B03_NATIVE_VALIDATION_GATE", ["PASS", "PASS_WITH_LIMITATIONS"]),
        _gate("C03A_RETRY_CONTROLLED_RENDER", "RENDER_GATE", ["C03A_RETRY_PASS_WITH_RENDER_LIMITATIONS_READY_FOR_P02", "C03A_RETRY_PASS_CONTROLLED_RENDER_REVIEW_READY_FOR_P02_PIPELINE_V2"]),
        _gate("B01_REVIEW_PACKET", "B01_REVIEW_GATE", ["REVIEW_READY", "REVIEW_READY_WITH_LIMITATIONS"]),
        _gate("CLAIM_BOUNDARY_CHECK", "CLAIM_BOUNDARY_GATE", ["PASS_WITH_LIMITATIONS"]),
        _gate("SCALEOUT_LOCK", "SCALEOUT_LOCK_GATE", ["BLOCKED"]),
    ]
    return {
        "schema": "pipeline_gate_contract.v1",
        "gate_status_values": ["PASS", "PASS_WITH_LIMITATIONS", "FAIL", "BLOCKED", "NOT_APPLICABLE", "INSUFFICIENT_EVIDENCE"],
        "gates": gates,
        "missing_b03_blocks": True,
        "missing_b01_blocks": True,
        "pass_with_limitations_is_product_pass": False,
        "scaleout_lock_must_remain_closed": True,
        "product_pass": False,
    }


def _gate(stage_id: str, gate_class: str, acceptable_statuses: list[str]) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "gate_class": gate_class,
        "acceptable_statuses": acceptable_statuses,
        "limitations_carried_forward": True,
        "product_pass_allowed": False,
        "scaleout_unlock_allowed": False,
    }
