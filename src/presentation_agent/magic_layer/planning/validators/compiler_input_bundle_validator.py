from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.presentation_agent.magic_layer.planning.validators.editable_candidate_spec_validator import validate_editable_candidate_spec


CANONICAL_OUTPUTS = {
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
}


def validate_compiler_input_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(bundle)
    failures: list[str] = []
    if data.get("schema") != "compiler_input_bundle.v1":
        failures.append("schema must be compiler_input_bundle.v1")
    for field in ("bundle_id", "editable_candidate_spec", "expected_outputs", "downstream_gates", "forbidden_outputs"):
        if field not in data:
            failures.append(f"{field} is required")
    if "B03_native_validation_gate" not in data.get("downstream_gates", []):
        failures.append("downstream B03 validation obligation is required")
    expected_outputs = [str(item).replace("\\", "/") for item in data.get("expected_outputs", [])]
    for output in expected_outputs:
        if output in CANONICAL_OUTPUTS:
            failures.append(f"canonical output target is forbidden: {output}")
        if "source_bound" in output.lower():
            failures.append(f"source-bound deck output is forbidden in T02: {output}")
    if data.get("created_pptx") is True:
        failures.append("T02 bundle must not create PPTX")
    spec_validation = validate_editable_candidate_spec(data.get("editable_candidate_spec", {}))
    if not spec_validation["pass"]:
        failures.append("editable candidate spec is invalid")
        failures.extend(spec_validation["failures"])
    return {
        "schema": "compiler_input_bundle_validation.v1",
        "pass": not failures,
        "failures": failures,
        "created_pptx": bool(data.get("created_pptx")),
        "product_pass": False,
    }
