from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.presentation_agent.magic_layer.planning.chart_table_planner import plan_chart_or_table
from src.presentation_agent.magic_layer.planning.compiler_input_bundle import build_compiler_input_bundle
from src.presentation_agent.magic_layer.planning.editable_candidate_spec import build_editable_candidate_spec
from src.presentation_agent.magic_layer.planning.icon_vector_planner import plan_icon_vector
from src.presentation_agent.magic_layer.planning.image_frame_planner import plan_image_frame
from src.presentation_agent.magic_layer.planning.shape_object_planner import plan_shape_object
from src.presentation_agent.magic_layer.planning.suppression_shape_planner import plan_suppression_shape
from src.presentation_agent.magic_layer.planning.text_object_planner import plan_text_object
from src.presentation_agent.magic_layer.planning.timeline_matrix_roadmap_planner import plan_structured_sequence
from src.presentation_agent.magic_layer.planning.validators.editable_candidate_spec_validator import validate_editable_candidate_spec
from src.presentation_agent.magic_layer.planning.validators.compiler_input_bundle_validator import validate_compiler_input_bundle
from src.presentation_agent.magic_layer.planning.validators.planner_input_validator import validate_planner_inputs
from src.presentation_agent.magic_layer.schemas.common import is_raster_target, is_semantic_object, is_semantic_text, is_structured_semantic


COMPILE_ELIGIBLE_DECISIONS = {"COMPILE_ELIGIBLE", "COMPILE_ELIGIBLE_WITH_WARNINGS", None, ""}


def plan_native_reconstruction(inputs: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(inputs)
    input_validation = validate_planner_inputs(data, sample_mode=bool(data.get("sample_mode")))
    if not input_validation["pass"]:
        return _blocked("PLAN_BLOCKED_MISSING_INPUT", input_validation["failures"])

    compile_decision = data.get("compile_eligibility_report", {}).get("decision")
    if compile_decision not in COMPILE_ELIGIBLE_DECISIONS:
        return _blocked("PLAN_BLOCKED_COMPILE_INELIGIBLE", [f"compile eligibility decision is {compile_decision}"])

    objects = _objects(data)
    slots = data.get("slot_schema", {}).get("slots", [])
    slot_by_id = {slot.get("slot_id"): slot for slot in slots}
    errors: list[str] = []
    warnings: list[str] = []
    reconstruction_objects: list[dict[str, Any]] = []

    for obj in objects:
        object_id = str(obj.get("object_id") or "object")
        if str(obj.get("object_kind", "")).lower() == "unknown" and obj.get("content_bearing"):
            return _blocked("PLAN_BLOCKED_UNKNOWN_LAYER", [f"{object_id}: unknown content-bearing object is fatal"])
        target = str(obj.get("pptx_target") or "")
        if _semantic_raster_violation(obj, target):
            return _blocked("PLAN_BLOCKED_SEMANTIC_RASTER", [f"{object_id}: semantic raster fallback is forbidden"])
        slot = slot_by_id.get(obj.get("slot_id")) or _slot_for_object(obj, slots)
        planned = _plan_object(obj, slot)
        if not planned.get("pass"):
            decision = planned.get("decision", "PLAN_INSUFFICIENT_EVIDENCE")
            return _blocked(decision, planned.get("failures", [f"{object_id}: planning failed"]))
        instruction = planned["instruction"]
        reconstruction_objects.append(_instruction_to_reconstruction(instruction))
        warnings.extend(planned.get("warnings", []))

    required_slots = {slot.get("slot_id") for slot in slots if slot.get("required") and slot.get("slot_id")}
    planned_slots = {item.get("slot_id") for item in reconstruction_objects if item.get("slot_id")}
    missing = sorted(required_slots - planned_slots)
    if missing:
        return _blocked("PLAN_BLOCKED_SLOT_SCHEMA", [f"{slot_id}: required slot missing reconstruction object" for slot_id in missing])

    native_plan = {
        "schema": "native_reconstruction_plan.v1",
        "plan_id": f"{data.get('template_contract', {}).get('template_id', 'template')}_native_plan",
        "template_id": data.get("template_contract", {}).get("template_id"),
        "archetype_id": data.get("template_contract", {}).get("archetype_id"),
        "source_protocol_refs": {
            "object_graph": bool(data.get("object_graph")),
            "layer_manifest": bool(data.get("layer_manifest")),
            "semantic_slot_graph": bool(data.get("semantic_slot_graph")),
        },
        "reconstruction_objects": reconstruction_objects,
        "z_order_plan": [{"object_id": item.get("object_id"), "z_order": item.get("z_order", 0)} for item in reconstruction_objects],
        "style_plan": {},
        "raster_policy": {"semantic_raster_allowed": False, "full_slide_raster_forbidden": True},
        "validation_summary": {"pass": not errors, "warnings": warnings, "errors": errors},
        "limitations": data.get("limitations", []),
        "review_hook_references": sorted({hook for item in reconstruction_objects for hook in item.get("review_hook_ids", [])}),
        "patch_hook_references": sorted({hook for item in reconstruction_objects for hook in item.get("patch_hook_ids", [])}),
    }
    editable_spec = build_editable_candidate_spec(native_plan, data["template_contract"], data["slot_schema"])
    bundle = build_compiler_input_bundle(editable_spec)
    spec_validation = validate_editable_candidate_spec(editable_spec)
    bundle_validation = validate_compiler_input_bundle(bundle)
    if not spec_validation["pass"]:
        return _blocked("PLAN_BLOCKED_SLOT_SCHEMA", spec_validation["failures"])
    if not bundle_validation["pass"]:
        return _blocked("PLAN_INSUFFICIENT_EVIDENCE", bundle_validation["failures"])
    return {
        "schema": "native_reconstruction_planner_result.v1",
        "decision": "PLAN_READY_WITH_WARNINGS" if warnings else "PLAN_READY",
        "planning_warnings": warnings,
        "planning_errors": errors,
        "compile_blockers": [],
        "review_hook_references": native_plan["review_hook_references"],
        "downstream_b03_obligations": ["B03_native_validation_gate"],
        "native_reconstruction_plan": native_plan,
        "editable_candidate_spec": editable_spec,
        "compiler_input_bundle": bundle,
        "editable_candidate_spec_validation": spec_validation,
        "compiler_input_bundle_validation": bundle_validation,
        "product_pass": False,
    }


def _objects(data: dict[str, Any]) -> list[dict[str, Any]]:
    objects = data.get("object_graph", {}).get("objects")
    if isinstance(objects, list) and objects:
        return objects
    return []


def _slot_for_object(obj: dict[str, Any], slots: list[dict[str, Any]]) -> dict[str, Any]:
    object_id = obj.get("object_id")
    for slot in slots:
        if object_id in slot.get("object_ids", []):
            return slot
    return {}


def _semantic_raster_violation(obj: dict[str, Any], target: str) -> bool:
    if is_raster_target(target):
        return is_semantic_object(obj)
    if obj.get("raster_allowed") is True and is_semantic_object(obj):
        return True
    return False


def _plan_object(obj: dict[str, Any], slot: dict[str, Any]) -> dict[str, Any]:
    slot_type = str(slot.get("slot_type") or obj.get("object_kind") or obj.get("semantic_role") or "").lower()
    if is_semantic_text(obj) or slot_type == "text":
        return plan_text_object(obj, slot)
    if slot_type == "image" or obj.get("pptx_target") == "replaceable_image_frame":
        return plan_image_frame(obj, slot)
    if slot_type in {"chart", "table"} or any(token in str(obj.get("semantic_role", "")).lower() for token in ("chart", "table")):
        return plan_chart_or_table(obj, slot)
    if slot_type in {"timeline", "matrix", "roadmap"} or is_structured_semantic(obj):
        return plan_structured_sequence(obj, slot)
    if slot_type == "icon":
        return plan_icon_vector(obj, slot)
    if str(obj.get("pptx_object_type")) == "suppression_shape":
        return plan_suppression_shape(obj, {"object_id": obj.get("replacement_editable_object_id"), "pptx_object_type": "text_box"})
    return plan_shape_object(obj, slot)


def _instruction_to_reconstruction(instruction: dict[str, Any]) -> dict[str, Any]:
    return {
        "reconstruction_id": instruction.get("instruction_id", "").replace("instr_", "recon_", 1),
        "object_id": instruction.get("object_id"),
        "layer_id": instruction.get("layer_id"),
        "slot_id": instruction.get("slot_id"),
        "semantic_role": instruction.get("semantic_role"),
        "pptx_object_type": instruction.get("pptx_object_type"),
        "geometry": instruction.get("geometry", {}),
        "style": instruction.get("style", {}),
        "text_content": instruction.get("text"),
        "data_content": instruction.get("data"),
        "image_frame_policy": instruction.get("image_frame"),
        "editability_guarantee": bool(instruction.get("editable_required", True)),
        "targetability": instruction.get("targetability", {}),
        "semantic_raster_allowed": False,
        "validation_checks": instruction.get("validation_checks", []),
        "review_hook_ids": instruction.get("review_hook_ids", []),
        "patch_hook_ids": instruction.get("patch_hook_ids", []),
        "limitations": [],
        "z_order": instruction.get("z_order", 0),
    }


def _blocked(decision: str, failures: list[str]) -> dict[str, Any]:
    return {
        "schema": "native_reconstruction_planner_result.v1",
        "decision": decision,
        "planning_warnings": [],
        "planning_errors": failures,
        "compile_blockers": failures,
        "review_hook_references": [],
        "downstream_b03_obligations": ["B03_native_validation_gate"],
        "native_reconstruction_plan": None,
        "editable_candidate_spec": None,
        "compiler_input_bundle": None,
        "product_pass": False,
    }
