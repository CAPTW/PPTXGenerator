from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.planning.geometry_resolver import bbox_norm_to_slide, object_bbox
from src.presentation_agent.magic_layer.planning.pptx_object_instruction import make_instruction
from src.presentation_agent.magic_layer.schemas.common import is_full_slide_bbox, is_semantic_text


def plan_image_frame(obj: dict[str, Any], slot: dict[str, Any] | None = None) -> dict[str, Any]:
    slot = slot or {}
    object_id = str(obj.get("object_id") or slot.get("slot_id") or "image")
    bbox = object_bbox(obj) or slot.get("bbox_norm")
    if is_full_slide_bbox(bbox):
        return {"pass": False, "decision": "PLAN_BLOCKED_SEMANTIC_RASTER", "failures": [f"{object_id}: full-slide image frame is forbidden"]}
    if obj.get("content_bearing") and is_semantic_text(obj) and not obj.get("suppression_plan_id"):
        return {"pass": False, "decision": "PLAN_BLOCKED_SEMANTIC_RASTER", "failures": [f"{object_id}: semantic image field text requires suppression and editable replacement"]}
    geometry = bbox_norm_to_slide(bbox)
    if not geometry.get("pass"):
        return {"pass": False, "decision": "PLAN_BLOCKED_SLOT_SCHEMA", "failures": geometry.get("failures", [])}
    instruction = make_instruction(
        instruction_id=f"instr_{object_id}",
        object_id=object_id,
        layer_id=obj.get("layer_id"),
        slot_id=slot.get("slot_id") or obj.get("slot_id"),
        pptx_object_type="replaceable_image_frame",
        geometry=geometry,
        semantic_role=str(obj.get("semantic_role") or slot.get("semantic_role") or "nonsemantic_image"),
        object_name=str(slot.get("pptx_object_name") or slot.get("slot_id") or object_id),
        editable_required=False,
        targetability={"selectable": True, "replaceable": True, "crop_editable": True, "style_editable": True},
        validation_checks=["bounded_replaceable_image_frame"],
        z_order=obj.get("z_order", obj.get("z_index", 0)),
        raster_allowed=True,
        image_frame={"replaceable": True, "bounded": True, "semantic": False},
    )
    return {"pass": True, "decision": "PLAN_READY", "instruction": instruction, "failures": []}
