from __future__ import annotations

from copy import deepcopy
from typing import Any


STRUCTURED_ROLES = {"chart", "table", "timeline", "matrix", "roadmap"}
RASTER_TYPES = {"replaceable_image_frame", "raster_image", "bounded_raster"}


def validate_native_reconstruction_plan(plan: dict[str, Any], slot_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    data = deepcopy(plan)
    failures: list[str] = []
    if data.get("schema", "native_reconstruction_plan.v1") != "native_reconstruction_plan.v1":
        failures.append("schema must be native_reconstruction_plan.v1")
    for field in ("plan_id", "template_id", "archetype_id", "reconstruction_objects"):
        if field not in data:
            failures.append(f"{field} is required")
    objects = data.get("reconstruction_objects", [])
    if not isinstance(objects, list):
        failures.append("reconstruction_objects must be a list")
        objects = []
    required_slot_ids = _required_slot_ids(slot_schema or {})
    reconstructed_slots = {obj.get("slot_id") for obj in objects if obj.get("slot_id")}
    for slot_id in sorted(required_slot_ids - reconstructed_slots):
        failures.append(f"{slot_id}: every required slot must have reconstruction object")
    for obj in objects:
        rid = obj.get("reconstruction_id", obj.get("object_id", "object"))
        role = str(obj.get("semantic_role", "")).lower()
        obj_type = str(obj.get("pptx_object_type", ""))
        if obj.get("semantic_raster_allowed") is True and _is_semantic(role):
            failures.append(f"{rid}: semantic_raster_allowed must be false")
        if any(token in role for token in STRUCTURED_ROLES) and obj_type in RASTER_TYPES:
            failures.append(f"{rid}: chart/table/timeline/matrix/roadmap raster fallback is forbidden")
        if obj_type == "suppression_shape" and not obj.get("replacement_editable_object_id"):
            failures.append(f"{rid}: suppression shape requires replacement editable object")
        if obj_type == "explicit_reject" and obj.get("required", True):
            failures.append(f"{rid}: explicit_reject on required component fails compile eligibility")
        if not obj.get("validation_checks"):
            failures.append(f"{rid}: reconstruction object must have validation checks")
    return {
        "schema": "native_reconstruction_plan_validation.v1",
        "pass": not failures,
        "compile_eligible": not failures,
        "failures": failures,
        "reconstruction_object_count": len(objects),
        "native_reconstruction_plan": data,
    }


def _required_slot_ids(slot_schema: dict[str, Any]) -> set[str]:
    return {slot.get("slot_id") for slot in slot_schema.get("slots", []) if slot.get("required") and slot.get("slot_id")}


def _is_semantic(role: str) -> bool:
    return any(token in role for token in ("text", "title", "subtitle", "body", "chart", "table", "timeline", "matrix", "roadmap", "footer", "source"))
