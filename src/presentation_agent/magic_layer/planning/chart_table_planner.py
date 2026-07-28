from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.planning.geometry_resolver import bbox_norm_to_slide
from src.presentation_agent.magic_layer.planning.pptx_object_instruction import make_instruction


CHART_TARGETS = {"native_chart", "editable_shape_chart"}
TABLE_TARGETS = {"native_table", "editable_shape_grid_table"}


def plan_chart_or_table(obj: dict[str, Any], slot: dict[str, Any]) -> dict[str, Any]:
    slot_type = str(slot.get("slot_type") or obj.get("object_kind") or obj.get("semantic_role") or "").lower()
    target = str(obj.get("pptx_target") or slot.get("native_target") or "")
    object_id = str(obj.get("object_id") or slot.get("slot_id") or slot_type or "structured")
    allowed = CHART_TARGETS if "chart" in slot_type else TABLE_TARGETS
    if target not in allowed:
        return {"pass": False, "decision": "PLAN_BLOCKED_NATIVE_COMPONENT", "failures": [f"{object_id}: {slot_type} raster fallback is forbidden"]}
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
        targetability={"selectable": True, "data_editable": target.startswith("native_"), "text_editable": True, "style_editable": True},
        validation_checks=[f"editable_{slot_type or 'structured'}"],
        z_order=obj.get("z_order", obj.get("z_index", 0)),
        raster_allowed=False,
        data=obj.get("data_content") or {"sample_only": True, "editable_geometry_policy": "approximate_allowed"},
        approximate_editable_geometry=not target.startswith("native_"),
    )
    return {"pass": bool(geometry.get("pass")), "decision": "PLAN_READY" if geometry.get("pass") else "PLAN_BLOCKED_SLOT_SCHEMA", "instruction": instruction, "failures": geometry.get("failures", [])}
