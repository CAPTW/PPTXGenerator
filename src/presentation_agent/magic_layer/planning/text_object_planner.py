from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.planning.geometry_resolver import bbox_norm_to_slide
from src.presentation_agent.magic_layer.planning.pptx_object_instruction import make_instruction


def plan_text_object(obj: dict[str, Any], slot: dict[str, Any]) -> dict[str, Any]:
    overflow_policy_id = slot.get("overflow_policy_id") or obj.get("overflow_policy_id")
    object_id = str(obj.get("object_id") or slot.get("object_ids", ["text"])[0])
    if not overflow_policy_id:
        return {"pass": False, "decision": "PLAN_BLOCKED_SLOT_SCHEMA", "failures": [f"{object_id}: semantic text requires overflow policy"]}
    geometry = bbox_norm_to_slide(obj.get("bbox_norm") or slot.get("bbox_norm"))
    if not geometry.get("pass"):
        return {"pass": False, "decision": "PLAN_BLOCKED_SLOT_SCHEMA", "failures": geometry.get("failures", [])}
    instruction = make_instruction(
        instruction_id=f"instr_{object_id}",
        object_id=object_id,
        layer_id=obj.get("layer_id"),
        slot_id=slot.get("slot_id") or obj.get("slot_id"),
        pptx_object_type="text_box",
        geometry=geometry,
        semantic_role=str(obj.get("semantic_role") or slot.get("semantic_role") or "text"),
        object_name=str(slot.get("pptx_object_name") or slot.get("slot_id") or object_id),
        targetability={"selectable": True, "independently_editable": True, "text_editable": True, "style_editable": True},
        validation_checks=["editable_text", "overflow_policy_attached"],
        overflow_policy_id=overflow_policy_id,
        text=obj.get("text_content") or {"placeholder": slot.get("placeholder_text", "TEXT")},
        z_order=obj.get("z_order", obj.get("z_index", 0)),
        raster_allowed=False,
    )
    return {"pass": True, "decision": "PLAN_READY", "instruction": instruction, "failures": []}
