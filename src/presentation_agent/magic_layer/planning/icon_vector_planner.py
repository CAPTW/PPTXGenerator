from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.planning.geometry_resolver import bbox_norm_to_slide
from src.presentation_agent.magic_layer.planning.pptx_object_instruction import make_instruction


def plan_icon_vector(obj: dict[str, Any], slot: dict[str, Any] | None = None) -> dict[str, Any]:
    slot = slot or {}
    object_id = str(obj.get("object_id") or slot.get("slot_id") or "icon")
    target = str(obj.get("pptx_target") or slot.get("native_target") or "svg_vector")
    if target in {"bounded_raster", "raster_image", "replaceable_image_frame"} and (obj.get("editable_required") or slot.get("required")):
        return {"pass": False, "decision": "PLAN_BLOCKED_NATIVE_COMPONENT", "failures": [f"{object_id}: required semantic icon cannot be raster"]}
    geometry = bbox_norm_to_slide(obj.get("bbox_norm") or slot.get("bbox_norm"))
    instruction = make_instruction(
        instruction_id=f"instr_{object_id}",
        object_id=object_id,
        layer_id=obj.get("layer_id"),
        slot_id=slot.get("slot_id") or obj.get("slot_id"),
        pptx_object_type="svg_icon" if target == "svg_vector" else "shape",
        geometry=geometry,
        semantic_role=str(obj.get("semantic_role") or slot.get("semantic_role") or "icon"),
        object_name=str(slot.get("pptx_object_name") or slot.get("slot_id") or object_id),
        targetability={"selectable": True, "style_editable": True},
        validation_checks=["editable_icon_or_svg"],
        z_order=obj.get("z_order", obj.get("z_index", 0)),
        raster_allowed=False,
    )
    return {"pass": bool(geometry.get("pass")), "decision": "PLAN_READY" if geometry.get("pass") else "PLAN_BLOCKED_SLOT_SCHEMA", "instruction": instruction, "failures": geometry.get("failures", [])}
