from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.schemas.common import bbox_valid
from src.presentation_agent.magic_layer.template.overflow_policy import validate_required_overflow_policies


def review_text_overflow(
    render_image: str | None = None,
    slots: list[dict[str, Any]] | None = None,
    ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slots = slots or []
    policy_status = validate_required_overflow_policies(slots)
    limitations: list[str] = []
    warnings: list[str] = []
    overlay_items: list[dict[str, Any]] = []
    patch_request_suggestions: list[dict[str, Any]] = []
    if ledger:
        overflow_count = int(ledger.get("text_overflow_count", ledger.get("overflow_count", 0)) or 0)
        status = "STRICT_LEDGER_CONFIRMED" if overflow_count == 0 else "HEURISTIC_RISK_DETECTED"
        return {
            "schema": "text_overflow_review.v1",
            "text_overflow_review_status": status,
            "text_overflow_count": overflow_count,
            "strict_pass_claimed": overflow_count == 0,
            "overflow_policy_status": "STRICT_LEDGER_BASED",
            "required_overflow_policy": policy_status,
            "per_slot_risks": [],
            "overlay_items": [],
            "patch_request_suggestions": [],
            "warnings": warnings,
            "limitations": limitations,
        }
    if not render_image:
        limitations.append("render image is missing; visual overflow review is limited")
        return {
            "schema": "text_overflow_review.v1",
            "text_overflow_review_status": "INSUFFICIENT_EVIDENCE",
            "text_overflow_count": None,
            "strict_pass_claimed": False,
            "overflow_policy_status": _policy_status(policy_status),
            "required_overflow_policy": policy_status,
            "per_slot_risks": [],
            "overlay_items": [],
            "patch_request_suggestions": [],
            "warnings": warnings,
            "limitations": limitations,
        }
    per_slot = []
    for index, slot in enumerate(slots):
        risk = _slot_overflow_risk(slot)
        per_slot.append(risk)
        if risk["risk_detected"]:
            overlay_items.append(
                {
                    "overlay_item_id": f"text_overflow_{slot.get('slot_id', index)}",
                    "slot_id": slot.get("slot_id"),
                    "category": "text_overflow_risk",
                    "label": slot.get("slot_id", "text overflow"),
                    "bbox_norm": slot.get("bbox_norm"),
                    "severity": "warning",
                    "draw_style": "outline",
                    "message": risk["reason"],
                }
            )
            patch_request_suggestions.append({"issue_type": "text_overflow", "patch_class": "PATCH_TEXT_OVERFLOW", "slot_id": slot.get("slot_id"), "bbox_norm": slot.get("bbox_norm")})
    status = "HEURISTIC_RISK_DETECTED" if overlay_items else "NO_RISK_DETECTED_HEURISTIC"
    if status == "NO_RISK_DETECTED_HEURISTIC":
        warnings.append("No strict overflow ledger exists; no-risk status is heuristic only.")
    return {
        "schema": "text_overflow_review.v1",
        "text_overflow_review_status": status,
        "text_overflow_count": len(overlay_items),
        "strict_pass_claimed": False,
        "overflow_policy_status": _policy_status(policy_status),
        "required_overflow_policy": policy_status,
        "per_slot_risks": per_slot,
        "overlay_items": overlay_items,
        "patch_request_suggestions": patch_request_suggestions,
        "warnings": warnings,
        "limitations": limitations or ["strict overflow validation requires ledger or reliable render review"],
    }


def _slot_overflow_risk(slot: dict[str, Any]) -> dict[str, Any]:
    bbox = slot.get("bbox_norm")
    text = str(slot.get("text_content") or slot.get("sample_text") or "")
    area = 0.0
    if bbox_valid(bbox):
        area = float(bbox[2]) * float(bbox[3])
    max_chars = int(slot.get("max_chars") or 0)
    risk = bool((text and area < 0.015 and len(text) > 40) or (max_chars and text and len(text) > max_chars))
    reason = "small text slot relative to text length" if risk else "no heuristic overflow risk"
    return {"slot_id": slot.get("slot_id"), "risk_detected": risk, "reason": reason, "bbox_norm": bbox, "text_length": len(text), "area": area}


def _policy_status(policy_status: dict[str, Any]) -> str:
    if policy_status.get("checked_slot_count", 0) == 0:
        return "NO_REQUIRED_NATIVE_TEXT_SLOTS"
    if policy_status.get("pass"):
        return "POLICY_REFERENCES_PRESENT"
    return "POLICY_REFERENCES_PARTIAL"
