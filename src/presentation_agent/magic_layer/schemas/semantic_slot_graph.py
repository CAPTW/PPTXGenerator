from __future__ import annotations

from typing import Any

from .common import bbox_valid, duplicate_ids


def validate_semantic_slot_graph(graph: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    slots = [item for item in graph.get("slots", []) if isinstance(item, dict)]
    for duplicate in duplicate_ids(slots, "slot_id"):
        failures.append(f"Duplicate slot id: {duplicate}")
    for slot in slots:
        slot_id = slot.get("slot_id", "<missing>")
        if not bbox_valid(slot.get("bbox_norm", [0.1, 0.1, 0.1, 0.1])):
            failures.append(f"Slot {slot_id} bbox_norm is invalid.")
        if slot.get("required") and not slot.get("object_ids"):
            failures.append(f"Required slot {slot_id} does not map to an object.")
        if slot.get("required") and slot.get("slot_type") == "text" and slot.get("native_target") != "ppt_text_box":
            failures.append(f"Required text slot {slot_id} must target ppt_text_box.")
    return {"schema_name": "semantic_slot_graph_validation", "pass": not failures, "slot_count": len(slots), "failures": failures, "warnings": []}
