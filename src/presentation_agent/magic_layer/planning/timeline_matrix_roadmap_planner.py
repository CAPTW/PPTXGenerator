from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.planning.geometry_resolver import bbox_norm_to_slide
from src.presentation_agent.magic_layer.planning.pptx_object_instruction import make_instruction


TARGET_BY_SLOT = {
    "timeline": "editable_timeline",
    "matrix": "editable_matrix",
    "roadmap": "editable_roadmap",
}


def plan_structured_sequence(obj: dict[str, Any], slot: dict[str, Any]) -> dict[str, Any]:
    slot_type = str(slot.get("slot_type") or obj.get("semantic_role") or "").lower()
    expected = TARGET_BY_SLOT.get(slot_type)
    target = str(obj.get("pptx_target") or slot.get("native_target") or "")
    object_id = str(obj.get("object_id") or slot.get("slot_id") or "structured")
    if not expected or target != expected:
        return {"pass": False, "decision": "PLAN_BLOCKED_NATIVE_COMPONENT", "failures": [f"{object_id}: {slot_type} must target {expected}"]}
    geometry = bbox_norm_to_slide(obj.get("bbox_norm") or slot.get("bbox_norm"))
    instruction = make_instruction(
        instruction_id=f"instr_{object_id}",
        object_id=object_id,
        layer_id=obj.get("layer_id"),
        slot_id=slot.get("slot_id") or obj.get("slot_id"),
        pptx_object_type=target,
        geometry=geometry,
        semantic_role=str(obj.get("semantic_role") or slot.get("semantic_role") or slot_type),
        object_name=str(slot.get("pptx_object_name") or slot.get("slot_id") or object_id),
        targetability={"selectable": True, "text_editable": True, "style_editable": True, "geometry_editable": True},
        validation_checks=[f"editable_{slot_type}"],
        z_order=obj.get("z_order", obj.get("z_index", 0)),
        raster_allowed=False,
    )
    return {"pass": bool(geometry.get("pass")), "decision": "PLAN_READY" if geometry.get("pass") else "PLAN_BLOCKED_SLOT_SCHEMA", "instruction": instruction, "failures": geometry.get("failures", [])}
