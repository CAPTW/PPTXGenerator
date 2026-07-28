from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.presentation_agent.magic_layer.planning.geometry_resolver import object_bbox, validate_bbox_norm
from src.presentation_agent.magic_layer.planning.pptx_object_instruction import validate_pptx_object_instruction
from src.presentation_agent.magic_layer.schemas.common import duplicate_ids, is_full_slide_bbox, is_semantic_object


def validate_editable_candidate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(spec)
    failures: list[str] = []
    if data.get("schema") != "editable_candidate_spec.v1":
        failures.append("schema must be editable_candidate_spec.v1")
    for field in ("spec_id", "template_id", "archetype_id", "pptx_setup", "objects", "slots"):
        if field not in data:
            failures.append(f"{field} is required")
    objects = data.get("objects", [])
    slots = data.get("slots", [])
    if not isinstance(objects, list):
        failures.append("objects must be a list")
        objects = []
    if not isinstance(slots, list):
        failures.append("slots must be a list")
        slots = []
    for duplicate in duplicate_ids(objects, "instruction_id"):
        failures.append(f"duplicate instruction_id: {duplicate}")
    for duplicate in duplicate_ids(objects, "object_id"):
        failures.append(f"duplicate object_id: {duplicate}")
    object_slot_ids = {obj.get("slot_id") for obj in objects if obj.get("slot_id")}
    for slot in slots:
        slot_id = slot.get("slot_id")
        if slot.get("required") and slot_id not in object_slot_ids:
            failures.append(f"{slot_id}: required slot without editable instruction")
    for obj in objects:
        ident = obj.get("instruction_id", obj.get("object_id", "instruction"))
        bbox_validation = validate_bbox_norm(object_bbox(obj))
        if not bbox_validation["pass"]:
            failures.append(f"{ident}: invalid bbox")
        if obj.get("pptx_object_type") in {"full_slide_raster", "screenshot_slide"}:
            failures.append(f"{ident}: full-slide raster and screenshot objects are forbidden")
        if obj.get("pptx_object_type") == "replaceable_image_frame" and is_full_slide_bbox(object_bbox(obj)):
            failures.append(f"{ident}: full-slide image instruction is forbidden")
        if obj.get("raster_allowed") is True and is_semantic_object(obj):
            failures.append(f"{ident}: semantic raster instruction is forbidden")
        if obj.get("editable_required", False) and not obj.get("object_name"):
            failures.append(f"{ident}: required editable instruction missing object_name")
        if obj.get("pptx_object_type") in {"native_chart", "native_table", "editable_shape_chart", "editable_shape_grid_table", "editable_timeline", "editable_matrix", "editable_roadmap"} and obj.get("raster_allowed"):
            failures.append(f"{ident}: native component cannot be raster fallback")
        instruction_validation = validate_pptx_object_instruction(obj)
        failures.extend(instruction_validation["failures"])
    if "B03_native_validation_gate" not in data.get("validation_requirements", []):
        failures.append("B03 downstream validation obligation is required")
    return {
        "schema": "editable_candidate_spec_validation.v1",
        "pass": not failures,
        "failures": failures,
        "object_count": len(objects),
        "slot_count": len(slots),
        "product_pass": False,
    }
