from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.presentation_agent.magic_layer.schemas.common import bbox_valid, duplicate_ids, is_full_slide_bbox


TEXT_TARGETS = {"ppt_text_box"}
IMAGE_TARGETS = {"replaceable_image_frame"}
CHART_TARGETS = {"native_chart", "editable_shape_chart", "explicit_reject"}
TABLE_TARGETS = {"native_table", "editable_shape_grid_table", "explicit_reject"}
STRUCTURED_TARGETS = {"editable_timeline", "editable_matrix", "editable_roadmap", "ppt_shape_group", "explicit_reject"}
RASTER_TARGETS = {"bounded_raster", "raster_image", "replaceable_image_frame"}


def validate_slot_schema(slot_schema: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(slot_schema)
    failures: list[str] = []
    if data.get("schema", "slot_schema.v1") != "slot_schema.v1":
        failures.append("schema must be slot_schema.v1")
    for field in ("schema_id", "template_id", "archetype_id", "slots"):
        if field not in data:
            failures.append(f"{field} is required")
    slots = data.get("slots", [])
    if not isinstance(slots, list):
        failures.append("slots must be a list")
        slots = []
    duplicates = duplicate_ids(slots, "slot_id")
    for slot_id in duplicates:
        failures.append(f"duplicate slot_id: {slot_id}")
    pptx_names = {}
    for slot in slots:
        slot_id = slot.get("slot_id", "")
        slot_type = str(slot.get("slot_type", "")).lower()
        target = str(slot.get("native_target", ""))
        required = bool(slot.get("required"))
        editable = bool(slot.get("editable"))
        bbox = _normalize_bbox(slot.get("bbox_norm"))
        if required and not bbox_valid(bbox):
            failures.append(f"{slot_id}: required slot must have bbox_norm")
        if required and not slot.get("validation_rule_ids"):
            failures.append(f"{slot_id}: required slot must have validation rules")
        if required and slot_type == "text":
            if target not in TEXT_TARGETS or not editable:
                failures.append(f"{slot_id}: required text slot must be editable and target ppt_text_box")
            if not slot.get("overflow_policy_id"):
                failures.append(f"{slot_id}: required text slot missing overflow policy")
        if slot_type == "image":
            if target not in IMAGE_TARGETS:
                failures.append(f"{slot_id}: image slot must target replaceable_image_frame")
            if bbox and is_full_slide_bbox(bbox):
                failures.append(f"{slot_id}: image slot must be bounded and not full-slide")
        if slot_type == "chart" and target not in CHART_TARGETS:
            failures.append(f"{slot_id}: chart slot must target native_chart or editable_shape_chart")
        if slot_type == "table" and target not in TABLE_TARGETS:
            failures.append(f"{slot_id}: table slot must target native_table or editable_shape_grid_table")
        if slot_type in {"timeline", "matrix", "roadmap"} and target not in STRUCTURED_TARGETS:
            failures.append(f"{slot_id}: {slot_type} slot must target editable PPT shape/group")
        if slot_type == "footer_source" and not editable:
            failures.append(f"{slot_id}: footer/source slot must be editable")
        if required and target in {"bounded_raster", "raster_image"}:
            failures.append(f"{slot_id}: semantic required slot cannot target raster")
        name = slot.get("pptx_object_name")
        if required and not name:
            failures.append(f"{slot_id}: required slot missing pptx_object_name")
        if name and required:
            if name in pptx_names:
                failures.append(f"{slot_id}: duplicate pptx_object_name for required slots")
            pptx_names[name] = slot_id
    return {"schema": "slot_schema_validation.v1", "pass": not failures, "failures": failures, "slot_count": len(slots), "slot_schema": data}


def _normalize_bbox(value: Any) -> list[float] | None:
    if isinstance(value, list) and len(value) == 4:
        return [float(item) for item in value]
    if isinstance(value, dict) and all(key in value for key in ("x", "y", "w", "h")):
        return [float(value["x"]), float(value["y"]), float(value["w"]), float(value["h"])]
    return None
