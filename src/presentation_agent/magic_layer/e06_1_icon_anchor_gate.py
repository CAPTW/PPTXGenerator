"""Icon and component anchor validation for E06.1."""

from __future__ import annotations

from typing import Any


def validate_icon_anchors(contract: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    slot_policies = policy.get("slot_policies", {})
    failures: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for slide in contract.get("slides", []):
        for icon in slide.get("semantic_icon_slots", []):
            slot_type = icon.get("slot_type")
            slot_policy = slot_policies.get(slot_type)
            center_inside = _center_inside(icon.get("bbox_norm", {}), icon.get("anchor_bbox_norm") or {})
            passed = bool(icon.get("anchor_object_id")) and bool(icon.get("anchor_component_id")) and bool(slot_policy) and center_inside
            row = {
                "slide_id": slide.get("slide_id"),
                "object_id": icon.get("object_id"),
                "semantic_role": icon.get("semantic_role"),
                "slot_type": slot_type,
                "anchor_component_id": icon.get("anchor_component_id"),
                "anchor_object_id": icon.get("anchor_object_id"),
                "anchor_position": icon.get("anchor_position"),
                "icon_center_inside_anchor": center_inside,
                "status": "passed" if passed else "failed",
            }
            rows.append(row)
            if not passed:
                failures.append({**row, "failure": "icon_anchor_invalid"})
    return {
        "schema_name": "icon_anchor_validation_report",
        "status": "passed" if not failures else "failed",
        "semantic_icon_count": len(rows),
        "icon_anchor_failure_count": len(failures),
        "rows": rows,
        "failures": failures,
    }


def validate_component_anchors(contract: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    semantic_count = 0
    for slide in contract.get("slides", []):
        for obj in slide.get("objects", []):
            if obj.get("object_type") == "semantic_icon":
                semantic_count += 1
                if not obj.get("anchor_object_id") or not obj.get("anchor_component_id"):
                    failures.append({"object_id": obj.get("object_id"), "failure": "unanchored_semantic_object"})
    return {
        "schema_name": "component_anchor_validation_report",
        "status": "passed" if not failures else "failed",
        "semantic_object_count": semantic_count,
        "unanchored_semantic_object_count": len(failures),
        "failures": failures,
    }


def _center_inside(bbox: dict[str, float], anchor: dict[str, float]) -> bool:
    if not bbox or not anchor:
        return False
    cx = float(bbox.get("x", 0)) + float(bbox.get("w", 0)) / 2
    cy = float(bbox.get("y", 0)) + float(bbox.get("h", 0)) / 2
    return float(anchor.get("x", 0)) <= cx <= float(anchor.get("x", 0)) + float(anchor.get("w", 0)) and float(anchor.get("y", 0)) <= cy <= float(anchor.get("y", 0)) + float(anchor.get("h", 0))
