from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.template.compile_eligibility_contract import compile_eligibility_contract
from src.presentation_agent.magic_layer.template.native_reconstruction_plan_v1 import validate_native_reconstruction_plan
from src.presentation_agent.magic_layer.template.slot_schema_v1 import validate_slot_schema
from src.presentation_agent.magic_layer.template.template_contract_v1 import validate_template_contract


def evaluate_compile_eligibility(
    protocol_report: dict[str, Any] | None = None,
    contract_validation: dict[str, Any] | None = None,
    slot_schema_validation: dict[str, Any] | None = None,
    native_plan_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    protocol_report = protocol_report or {"status": "PASS"}
    contract_validation = contract_validation or {"pass": False, "failures": ["contract validation missing"]}
    slot_schema_validation = slot_schema_validation or {"pass": False, "failures": ["slot schema validation missing"]}
    native_plan_validation = native_plan_validation or {"pass": False, "failures": ["native plan validation missing"], "compile_eligible": False}
    blockers = []
    if protocol_report.get("unknown_content_bearing_count", 0) > 0 or protocol_report.get("semantic_raster_violation_count", 0) > 0 or protocol_report.get("full_slide_raster_plan_count", 0) > 0:
        decision = "BLOCKED_FATAL_POLICY"
        blockers.append("fatal protocol policy violation")
    elif protocol_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS", None}:
        decision = "BLOCKED_FATAL_POLICY"
        blockers.append("protocol gate not pass")
    elif not contract_validation.get("pass") or not slot_schema_validation.get("pass") or not native_plan_validation.get("pass") or not native_plan_validation.get("compile_eligible", False):
        decision = "NOT_COMPILE_ELIGIBLE"
        blockers.extend(contract_validation.get("failures", []))
        blockers.extend(slot_schema_validation.get("failures", []))
        blockers.extend(native_plan_validation.get("failures", []))
    else:
        decision = "COMPILE_ELIGIBLE"
    contract = compile_eligibility_contract()
    return {
        "schema": "compile_eligibility_report.v1",
        "decision": decision,
        "blocked_conditions": blockers,
        "downstream_validation_obligations": contract["downstream_validation_obligations"],
        "review_obligations": contract["review_obligations"],
        "product_pass": False,
        "compile_performed": False,
    }


def evaluate_compile_eligibility_files(contract: str | Path, slot_schema: str | Path, native_plan: str | Path, protocol_report: str | Path | None = None) -> dict[str, Any]:
    contract_data = json.loads(Path(contract).read_text(encoding="utf-8"))
    slot_data = json.loads(Path(slot_schema).read_text(encoding="utf-8"))
    plan_data = json.loads(Path(native_plan).read_text(encoding="utf-8"))
    protocol = json.loads(Path(protocol_report).read_text(encoding="utf-8")) if protocol_report else {"status": "PASS"}
    return evaluate_compile_eligibility(
        protocol_report=protocol,
        contract_validation=validate_template_contract(contract_data),
        slot_schema_validation=validate_slot_schema(slot_data),
        native_plan_validation=validate_native_reconstruction_plan(plan_data, slot_data),
    )
