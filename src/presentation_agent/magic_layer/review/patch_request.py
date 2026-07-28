from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.presentation_agent.magic_layer.schemas.common import bbox_valid

from .visual_issue_taxonomy import recommended_patch_class


FORBIDDEN_ACTIONS = [
    "generate_image",
    "full_slide_raster",
    "semantic_raster_fallback",
    "screenshot_slide",
    "source_bound_generation",
    "canonical_promotion",
]
DEFAULT_ACCEPTANCE_CHECKS = ["protocol_gate", "b03_native_validation_gate", "render_review"]


def validate_patch_request(request: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    normalized = deepcopy(request)
    normalized.setdefault("schema", "patch_request.v1")
    normalized.setdefault("forbidden_actions", [])
    normalized.setdefault("acceptance_checks", [])
    normalized.setdefault("applied_patch", False)
    for action in FORBIDDEN_ACTIONS:
        if action not in normalized["forbidden_actions"]:
            normalized["forbidden_actions"].append(action)
    for field in ("patch_request_id", "source_review_packet_id", "issue_ids", "patch_class"):
        if not normalized.get(field):
            failures.append(f"{field} is required")
    if normalized.get("bbox_norm") is not None and not bbox_valid(normalized["bbox_norm"]):
        failures.append("bbox_norm invalid")
    for check in DEFAULT_ACCEPTANCE_CHECKS:
        if check not in normalized["acceptance_checks"]:
            failures.append(f"acceptance check missing: {check}")
    if normalized.get("applied_patch") is not False:
        failures.append("patch request must not be marked as applied")
    return {"schema": "patch_request_validation.v1", "pass": not failures, "failures": failures, "request": normalized}


def create_patch_request_from_issue(review_packet: dict[str, Any], issue_id: str) -> dict[str, Any]:
    issues = review_packet.get("visual_issues", [])
    issue = next((item for item in issues if item.get("issue_id") == issue_id), {"issue_id": issue_id, "issue_type": "visual_geometry_drift"})
    patch_class = issue.get("recommended_patch_class") or recommended_patch_class(str(issue.get("issue_type", "")))
    target_objects = [issue["object_id"]] if issue.get("object_id") else []
    target_layers = [issue["layer_id"]] if issue.get("layer_id") else []
    target_slots = [issue["slot_id"]] if issue.get("slot_id") else []
    return {
        "schema": "patch_request.v1",
        "patch_request_id": f"patch_{issue_id}",
        "source_review_packet_id": review_packet.get("packet_id", "review_packet"),
        "issue_ids": [issue_id],
        "patch_class": patch_class,
        "target_objects": target_objects,
        "target_layers": target_layers,
        "target_slots": target_slots,
        "target_selections": [issue["selection_id"]] if issue.get("selection_id") else [],
        "bbox_norm": issue.get("bbox_norm"),
        "patch_scope": "single_object" if target_objects or target_layers else "selected_region",
        "allowed_actions": _allowed_actions_for_patch(patch_class),
        "forbidden_actions": FORBIDDEN_ACTIONS.copy(),
        "acceptance_checks": DEFAULT_ACCEPTANCE_CHECKS.copy(),
        "evidence_paths": issue.get("evidence_paths", []),
        "notes": "Patch request is not an applied patch and cannot authorize generation, scaleout, or canonical promotion.",
        "applied_patch": False,
    }


def _allowed_actions_for_patch(patch_class: str) -> list[str]:
    mapping = {
        "PATCH_TEXT_REGION_LIFT": ["update_bbox", "add_editable_text", "add_native_cover_shape", "adjust_z_order"],
        "PATCH_RASTER_TEXT_SUPPRESSION": ["add_native_cover_shape", "add_editable_text", "adjust_z_order"],
        "PATCH_TEXT_OVERFLOW": ["adjust_text_style", "update_bbox"],
        "PATCH_NATIVE_PLATE_STYLE": ["adjust_shape_style", "adjust_z_order"],
        "PATCH_CHART_NATIVE_RECONSTRUCTION": ["update_bbox", "explicit_reject"],
        "PATCH_TABLE_NATIVE_RECONSTRUCTION": ["update_bbox", "explicit_reject"],
        "PATCH_UNKNOWN_LAYER_CLASSIFICATION": ["reclassify_unknown_with_evidence", "explicit_reject"],
        "PATCH_SLOT_SCHEMA": ["update_bbox", "explicit_reject"],
        "PATCH_OBJECT_BBOX": ["update_bbox"],
        "PATCH_Z_ORDER": ["adjust_z_order"],
        "PATCH_RENDER_FIDELITY": ["adjust_shape_style", "replace_nonsemantic_image_frame"],
    }
    return mapping.get(patch_class, ["update_bbox"])
