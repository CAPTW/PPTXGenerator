from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.planning.geometry_resolver import bbox_norm_to_slide, object_bbox
from src.presentation_agent.magic_layer.planning.pptx_object_instruction import make_instruction
from src.presentation_agent.magic_layer.schemas.common import is_full_slide_bbox


def plan_suppression_shape(suppression: dict[str, Any], replacement: dict[str, Any] | None) -> dict[str, Any]:
    object_id = str(suppression.get("object_id") or "suppression_shape")
    if not replacement or not replacement.get("object_id"):
        return {"pass": False, "decision": "PLAN_BLOCKED_SEMANTIC_RASTER", "failures": [f"{object_id}: semantic raster suppression requires replacement editable text"]}
    bbox = object_bbox(suppression)
    if is_full_slide_bbox(bbox):
        return {"pass": False, "decision": "PLAN_BLOCKED_SEMANTIC_RASTER", "failures": [f"{object_id}: suppression shape must not be full-slide"]}
    geometry = bbox_norm_to_slide(bbox)
    instruction = make_instruction(
        instruction_id=f"instr_{object_id}",
        object_id=object_id,
        pptx_object_type="suppression_shape",
        geometry=geometry,
        semantic_role="suppression_shape",
        object_name=object_id,
        targetability={"selectable": True, "style_editable": True, "geometry_editable": True},
        validation_checks=["native_suppression_shape", "editable_replacement_required"],
        review_hook_ids=["native_plate_visual_risk"],
        patch_hook_ids=["PATCH_NATIVE_PLATE_STYLE", "PATCH_RASTER_TEXT_SUPPRESSION"],
        suppresses_object_id=suppression.get("suppresses_object_id"),
        replacement_editable_object_id=replacement.get("object_id"),
        z_order=suppression.get("z_order", 0),
        raster_allowed=False,
    )
    return {"pass": bool(geometry.get("pass")), "decision": "PLAN_READY" if geometry.get("pass") else "PLAN_BLOCKED_SLOT_SCHEMA", "instruction": instruction, "failures": geometry.get("failures", [])}
