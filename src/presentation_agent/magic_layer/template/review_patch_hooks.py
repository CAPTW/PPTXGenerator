from __future__ import annotations

from typing import Any


FORBIDDEN_PATCH_ACTIONS = ["generate_image", "semantic_raster_fallback", "full_slide_raster", "screenshot_slide", "source_bound_generation", "canonical_promotion"]
ACCEPTANCE_CHECKS = ["E01P_protocol_gate", "T01_contract_gate", "B03_native_validation_gate", "B01_render_review_if_visual_risk"]


def build_review_hook(slot_id: str, issue_types: list[str], required_review: str = "heuristic_review") -> dict[str, Any]:
    return {
        "review_hook_id": f"review_{slot_id.lower()}",
        "slot_id": slot_id,
        "issue_types": issue_types,
        "required_review": required_review,
        "evidence_required": ["B01_review_packet"],
        "b01_issue_mapping": issue_types,
        "blocks_compile": required_review in {"strict_ledger_review", "manual_review"},
        "blocks_product_pass": required_review != "none",
    }


def build_patch_hook(slot_id: str, allowed_patch_classes: list[str]) -> dict[str, Any]:
    return {
        "patch_hook_id": f"patch_{slot_id.lower()}",
        "slot_id": slot_id,
        "allowed_patch_classes": allowed_patch_classes,
        "forbidden_patch_actions": FORBIDDEN_PATCH_ACTIONS.copy(),
        "acceptance_checks": ACCEPTANCE_CHECKS.copy(),
        "patch_scope_required": True,
        "applied_patch": False,
    }


def validate_patch_hook(hook: dict[str, Any]) -> dict[str, Any]:
    failures = []
    for action in FORBIDDEN_PATCH_ACTIONS:
        if action not in hook.get("forbidden_patch_actions", []):
            failures.append(f"forbidden action missing: {action}")
    for check in ACCEPTANCE_CHECKS:
        if check not in hook.get("acceptance_checks", []):
            failures.append(f"acceptance check missing: {check}")
    if hook.get("applied_patch") is not False:
        failures.append("patch hook must not mark patch as applied")
    return {"pass": not failures, "failures": failures}
