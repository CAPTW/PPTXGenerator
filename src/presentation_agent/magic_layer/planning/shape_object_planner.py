from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.planning.geometry_resolver import bbox_norm_to_slide
from src.presentation_agent.magic_layer.planning.pptx_object_instruction import make_instruction


def plan_shape_object(obj: dict[str, Any], slot: dict[str, Any] | None = None) -> dict[str, Any]:
    slot = slot or {}
    object_id = str(obj.get("object_id") or slot.get("slot_id") or "shape")
    geometry = bbox_norm_to_slide(obj.get("bbox_norm") or slot.get("bbox_norm"))
    if not geometry.get("pass"):
        return {"pass": False, "decision": "PLAN_BLOCKED_SLOT_SCHEMA", "failures": geometry.get("failures", [])}
    role = str(obj.get("semantic_role") or slot.get("semantic_role") or slot.get("slot_type") or "shape")
    object_type = "group" if any(token in role.lower() for token in ("card", "panel", "group")) else "shape"
    instruction = make_instruction(
        instruction_id=f"instr_{object_id}",
        object_id=object_id,
        layer_id=obj.get("layer_id"),
        slot_id=slot.get("slot_id") or obj.get("slot_id"),
        pptx_object_type=object_type,
        geometry=geometry,
        semantic_role=role,
        object_name=str(slot.get("pptx_object_name") or slot.get("slot_id") or object_id),
        targetability={"selectable": True, "style_editable": True, "geometry_editable": True},
        validation_checks=["editable_shape"],
        z_order=obj.get("z_order", obj.get("z_index", 0)),
        raster_allowed=False,
    )
    return {"pass": True, "decision": "PLAN_READY", "instruction": instruction, "failures": []}
