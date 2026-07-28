from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.compiler.pptx_primitive import map_instruction_to_primitive, validate_primitive
from src.presentation_agent.magic_layer.planning.geometry_resolver import object_bbox
from src.presentation_agent.magic_layer.schemas.common import is_full_slide_bbox


def map_suppression_shape(instruction: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if not instruction.get("suppresses_object_id") or not instruction.get("replacement_editable_object_id"):
        failures.append("suppression shape requires suppressed and replacement editable object ids")
    if is_full_slide_bbox(object_bbox(instruction)):
        failures.append("suppression shape cannot be full-slide")
    primitive = map_instruction_to_primitive(instruction)
    for hook in instruction.get("review_hook_ids", []):
        if hook not in primitive["validation_checks"]:
            primitive["validation_checks"].append(hook)
    validation = validate_primitive(primitive)
    failures.extend(validation["failures"])
    return {"schema": "suppression_shape_mapping_result.v1", "pass": not failures, "primitive": primitive, "failures": failures}
