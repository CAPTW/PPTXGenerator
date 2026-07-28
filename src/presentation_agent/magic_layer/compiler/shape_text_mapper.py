from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.compiler.pptx_primitive import map_instruction_to_primitive, validate_primitive


def map_shape_or_text(instruction: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if instruction.get("pptx_object_type") == "text_box":
        if instruction.get("editable_required", True) and not instruction.get("text"):
            failures.append("required text must preserve text payload")
        if instruction.get("editable_required", True) and not instruction.get("overflow_policy_id"):
            failures.append("required text must preserve overflow policy ref")
    primitive = map_instruction_to_primitive(instruction)
    if instruction.get("semantic_role") == "footer_source":
        primitive["editability_contract"]["text_editable"] = True
    validation = validate_primitive(primitive)
    failures.extend(validation["failures"])
    return {"schema": "shape_text_mapping_result.v1", "pass": not failures, "primitive": primitive, "failures": failures}
