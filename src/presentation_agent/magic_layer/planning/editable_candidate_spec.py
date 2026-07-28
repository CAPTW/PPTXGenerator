from __future__ import annotations

from copy import deepcopy
from typing import Any


def minimal_editable_candidate_spec() -> dict[str, Any]:
    return {
        "schema": "editable_candidate_spec.v1",
        "spec_id": "sample_minimal_cover_hero_spec",
        "template_id": "tpl_cover",
        "archetype_id": "cover_hero",
        "source_reference_id": "sample_only",
        "source_protocol_refs": {"sample_only": True, "product_evidence": False},
        "canvas": {"ratio": "16:9", "slide_width_in": 13.333, "slide_height_in": 7.5},
        "pptx_setup": {"slide_width_in": 13.333, "slide_height_in": 7.5, "ratio": "16:9"},
        "objects": [
            {
                "instruction_id": "instr_obj_title",
                "object_id": "obj_title",
                "layer_id": "layer_title",
                "slot_id": "SLOT_TITLE",
                "pptx_object_type": "text_box",
                "geometry": {"bbox_norm": [0.1, 0.1, 0.6, 0.12]},
                "style": {},
                "text": {"placeholder": "TITLE"},
                "overflow_policy_id": "ov_title",
                "targetability": {"selectable": True, "independently_editable": True, "text_editable": True, "style_editable": True},
                "editable_required": True,
                "semantic_role": "title",
                "raster_allowed": False,
                "object_name": "SLOT_TITLE",
                "validation_checks": ["editable_text", "overflow_policy_attached"],
                "review_hook_ids": ["text_overflow_review"],
                "patch_hook_ids": ["PATCH_TEXT_OVERFLOW"],
            }
        ],
        "groups": [],
        "slots": [
            {
                "slot_id": "SLOT_TITLE",
                "slot_type": "text",
                "required": True,
                "editable": True,
                "object_ids": ["obj_title"],
                "native_target": "ppt_text_box",
                "overflow_policy_id": "ov_title",
                "pptx_object_name": "SLOT_TITLE",
            }
        ],
        "z_order": [{"object_id": "obj_title", "resolved_z_order": 1}],
        "style_tokens": {},
        "media_assets": [],
        "validation_requirements": ["E01P_protocol_gate", "T01_contract_gate", "B03_native_validation_gate"],
        "review_hooks": ["text_overflow_review"],
        "patch_hooks": ["PATCH_TEXT_OVERFLOW"],
        "provenance": {"sample_only": True, "generated_for_tests": True, "product_evidence": False},
        "limitations": ["sample_only_not_product_evidence"],
        "product_pass": False,
    }


def build_editable_candidate_spec(
    native_plan: dict[str, Any],
    contract: dict[str, Any],
    slot_schema: dict[str, Any],
) -> dict[str, Any]:
    plan = deepcopy(native_plan)
    slots = deepcopy(slot_schema.get("slots", []))
    slot_by_id = {slot.get("slot_id"): slot for slot in slots}
    instructions: list[dict[str, Any]] = []
    for reconstruction in plan.get("reconstruction_objects", []):
        slot = slot_by_id.get(reconstruction.get("slot_id"), {})
        object_type = reconstruction.get("pptx_object_type")
        instruction = {
            "instruction_id": f"instr_{reconstruction.get('object_id') or reconstruction.get('reconstruction_id')}",
            "object_id": reconstruction.get("object_id"),
            "layer_id": reconstruction.get("layer_id"),
            "slot_id": reconstruction.get("slot_id"),
            "pptx_object_type": object_type,
            "geometry": reconstruction.get("geometry", {}),
            "style": reconstruction.get("style", {}),
            "text": reconstruction.get("text_content", reconstruction.get("text")),
            "data": reconstruction.get("data_content", reconstruction.get("data")),
            "image_frame": reconstruction.get("image_frame_policy"),
            "targetability": reconstruction.get("targetability", {}),
            "editable_required": slot.get("required", reconstruction.get("editable_required", True)),
            "semantic_role": reconstruction.get("semantic_role", slot.get("semantic_role", "")),
            "raster_allowed": reconstruction.get("semantic_raster_allowed", False) is True,
            "object_name": slot.get("pptx_object_name") or reconstruction.get("object_name") or reconstruction.get("slot_id") or reconstruction.get("object_id"),
            "overflow_policy_id": slot.get("overflow_policy_id") or reconstruction.get("overflow_policy_id"),
            "validation_checks": reconstruction.get("validation_checks", []),
            "review_hook_ids": reconstruction.get("review_hook_ids", []),
            "patch_hook_ids": reconstruction.get("patch_hook_ids", []),
        }
        instructions.append({key: value for key, value in instruction.items() if value is not None})
    return {
        "schema": "editable_candidate_spec.v1",
        "spec_id": f"{plan.get('plan_id', 'native_plan')}_editable_candidate_spec",
        "template_id": contract.get("template_id") or plan.get("template_id"),
        "archetype_id": contract.get("archetype_id") or plan.get("archetype_id"),
        "source_reference_id": contract.get("source_reference_id"),
        "source_protocol_refs": plan.get("source_protocol_refs", {}),
        "canvas": contract.get("canvas", {"ratio": "16:9"}),
        "pptx_setup": {"slide_width_in": contract.get("canvas", {}).get("slide_width_in", 13.333), "slide_height_in": contract.get("canvas", {}).get("slide_height_in", 7.5), "ratio": "16:9"},
        "objects": instructions,
        "groups": [],
        "slots": slots,
        "z_order": plan.get("z_order_plan", []),
        "style_tokens": contract.get("design_tokens", {}),
        "media_assets": [],
        "validation_requirements": ["E01P_protocol_gate", "T01_contract_gate", "B03_native_validation_gate"],
        "review_hooks": plan.get("review_hook_references", []),
        "patch_hooks": plan.get("patch_hook_references", []),
        "provenance": {"source": "T02_native_reconstruction_planner", "product_evidence": False},
        "limitations": plan.get("limitations", []),
        "product_pass": False,
    }
