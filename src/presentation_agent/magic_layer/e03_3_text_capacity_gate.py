"""Text capacity gate for E03.3."""

from __future__ import annotations

from typing import Any


def build_text_capacity_report(archetype: str, graph: dict[str, Any]) -> dict[str, Any]:
    rows = []
    overflow = 0
    for node in graph["nodes"]:
        if node.get("object_type") != "text":
            continue
        bbox = node["bbox_norm"]
        area = max(0.0001, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
        capacity = int(area * 900)
        text = node.get("text", "")
        passed = len(text) <= capacity
        if not passed:
            overflow += 1
        rows.append({"object_id": node["object_id"], "text_length": len(text), "capacity_estimate": capacity, "status": "passed" if passed else "failed"})
    return {"schema_name": "text_capacity_report", "status": "passed" if overflow == 0 else "failed", "archetype_id": archetype, "text_overflow_count": overflow, "text_clipping_count": 0, "rows": rows}
