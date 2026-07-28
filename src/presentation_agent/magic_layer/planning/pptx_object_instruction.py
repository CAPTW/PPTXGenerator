from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.presentation_agent.magic_layer.planning.geometry_resolver import object_bbox
from src.presentation_agent.magic_layer.schemas.common import is_full_slide_bbox, is_semantic_object


RASTER_OBJECT_TYPES = {"raster_image", "bounded_raster", "full_slide_raster", "screenshot_slide"}
NATIVE_STRUCTURED_TYPES = {
    "native_chart",
    "native_table",
    "editable_shape_chart",
    "editable_shape_grid_table",
    "editable_timeline",
    "editable_matrix",
    "editable_roadmap",
}


def make_instruction(
    *,
    instruction_id: str,
    object_id: str,
    pptx_object_type: str,
    geometry: dict[str, Any],
    semantic_role: str,
    object_name: str,
    slot_id: str | None = None,
    layer_id: str | None = None,
    style: dict[str, Any] | None = None,
    targetability: dict[str, Any] | None = None,
    validation_checks: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    instruction = {
        "instruction_id": instruction_id,
        "object_id": object_id,
        "layer_id": layer_id,
        "slot_id": slot_id,
        "pptx_object_type": pptx_object_type,
        "geometry": geometry,
        "style": style or {},
        "z_order": extra.pop("z_order", 0),
        "semantic_role": semantic_role,
        "editable_required": extra.pop("editable_required", True),
        "targetability": targetability or {},
        "raster_allowed": extra.pop("raster_allowed", False),
        "object_name": object_name,
        "validation_checks": validation_checks or [],
        "review_hook_ids": extra.pop("review_hook_ids", []),
        "patch_hook_ids": extra.pop("patch_hook_ids", []),
    }
    instruction.update({key: value for key, value in extra.items() if value is not None})
    return instruction


def validate_pptx_object_instruction(instruction: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(instruction)
    failures: list[str] = []
    object_type = str(data.get("pptx_object_type", ""))
    bbox = object_bbox(data)
    if object_type in {"full_slide_raster", "screenshot_slide"}:
        failures.append(f"{data.get('instruction_id', 'instruction')}: full-slide raster and screenshot objects are forbidden")
    if object_type == "replaceable_image_frame":
        if is_full_slide_bbox(bbox):
            failures.append(f"{data.get('instruction_id', 'instruction')}: replaceable image frame must be bounded")
        if is_semantic_object(data):
            failures.append(f"{data.get('instruction_id', 'instruction')}: replaceable image frame must be nonsemantic")
        targetability = data.get("targetability", {})
        if not targetability.get("replaceable") or not targetability.get("crop_editable"):
            failures.append(f"{data.get('instruction_id', 'instruction')}: image frame requires replaceable and crop_editable targetability")
    if object_type == "text_box":
        if "text" not in data:
            failures.append(f"{data.get('instruction_id', 'instruction')}: text box requires text payload")
        if not data.get("overflow_policy_id"):
            failures.append(f"{data.get('instruction_id', 'instruction')}: text box requires overflow policy")
    if object_type == "native_chart" and not (data.get("data") or data.get("approximate_editable_geometry")):
        failures.append(f"{data.get('instruction_id', 'instruction')}: native chart requires data or approximate editable geometry policy")
    if object_type == "native_table" and not (data.get("data") or data.get("table_schema")):
        failures.append(f"{data.get('instruction_id', 'instruction')}: native table requires data or table schema")
    if object_type == "suppression_shape":
        if is_full_slide_bbox(bbox):
            failures.append(f"{data.get('instruction_id', 'instruction')}: suppression shape must not be full-slide")
        if not data.get("suppresses_object_id") or not data.get("replacement_editable_object_id"):
            failures.append(f"{data.get('instruction_id', 'instruction')}: suppression shape requires suppressed and replacement editable object ids")
    if data.get("raster_allowed") is True and is_semantic_object(data):
        failures.append(f"{data.get('instruction_id', 'instruction')}: semantic instruction cannot allow raster")
    return {"schema": "pptx_object_instruction_validation.v1", "pass": not failures, "failures": failures, "instruction": data}
