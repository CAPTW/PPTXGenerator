from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.compiler.pptx_primitive import map_instruction_to_primitive, validate_primitive
from src.presentation_agent.magic_layer.planning.geometry_resolver import object_bbox
from src.presentation_agent.magic_layer.schemas.common import is_full_slide_bbox, is_semantic_object


def map_image_frame(instruction: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if instruction.get("pptx_object_type") != "replaceable_image_frame":
        failures.append("image frame mapper only accepts replaceable_image_frame")
    if is_full_slide_bbox(object_bbox(instruction)):
        failures.append("full-slide image frame blocks compile")
    if is_semantic_object(instruction):
        failures.append("semantic image asset blocks compile")
    targetability = instruction.get("targetability", {})
    if not targetability.get("replaceable") or not targetability.get("crop_editable"):
        failures.append("image frame requires replaceable/crop_editable targetability")
    primitive = map_instruction_to_primitive(instruction)
    validation = validate_primitive(primitive)
    failures.extend(validation["failures"])
    return {"schema": "image_frame_mapping_result.v1", "pass": not failures, "primitive": primitive, "failures": failures}
