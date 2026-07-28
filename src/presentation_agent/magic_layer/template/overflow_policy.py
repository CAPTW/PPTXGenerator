from __future__ import annotations

from typing import Any


VALID_MODES = {"STRICT_LEDGER_BASED", "HEURISTIC_OOXML_BASED", "VISUAL_REVIEW_REQUIRED", "NOT_VALIDATED"}
VALID_BEHAVIORS = {"fail_on_overflow", "reduce_font_until_min", "allow_manual_review", "create_continuation_later"}


def validate_overflow_policy(policy: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if not policy.get("overflow_policy_id"):
        failures.append("overflow_policy_id is required")
    if policy.get("behavior") and policy["behavior"] not in VALID_BEHAVIORS:
        failures.append("invalid overflow behavior")
    if policy.get("current_validation_mode", "HEURISTIC_OOXML_BASED") not in VALID_MODES:
        failures.append("invalid current_validation_mode")
    if policy.get("behavior") == "truncate_silently":
        failures.append("silent truncation is forbidden")
    if policy.get("strict_validation_required") and policy.get("current_validation_mode") != "STRICT_LEDGER_BASED":
        failures.append("strict overflow pass requires strict ledger mode")
    return {"pass": not failures, "failures": failures, "strict_pass_claimed": policy.get("current_validation_mode") == "STRICT_LEDGER_BASED"}


def validate_required_overflow_policies(slots: list[dict[str, Any]]) -> dict[str, Any]:
    missing = []
    checked = []
    for slot in slots:
        slot_id = str(slot.get("slot_id") or slot.get("object_name") or "")
        role = str(slot.get("semantic_role") or slot.get("role") or slot_id).lower()
        required = bool(slot.get("editable_required", True))
        is_native_label = any(token in role or token in slot_id.lower() for token in ("kpi", "chart", "table", "cell", "label", "axis"))
        if required and is_native_label:
            checked.append(slot_id)
            if not slot.get("overflow_policy_id"):
                missing.append(slot_id)
    return {
        "schema": "required_overflow_policy_check.v1",
        "checked_slot_count": len(checked),
        "missing_policy_count": len(missing),
        "missing_policy_slots": missing,
        "pass": not missing,
        "strict_pass_claimed": False,
        "product_pass": False,
    }
