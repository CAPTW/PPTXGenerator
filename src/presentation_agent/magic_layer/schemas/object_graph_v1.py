from __future__ import annotations

from typing import Any

from .common import bbox_valid, duplicate_ids


def validate_object_graph(graph: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    objects = [item for item in graph.get("objects", []) if isinstance(item, dict)]
    for duplicate in duplicate_ids(objects, "object_id"):
        failures.append(f"Duplicate object id: {duplicate}")
    for obj in objects:
        object_id = obj.get("object_id", "<missing>")
        if not obj.get("object_id"):
            failures.append("Object requires object_id.")
        if not bbox_valid(obj.get("bbox_norm")):
            failures.append(f"Object {object_id} bbox_norm is invalid.")
    return {"schema_name": "object_graph_v1_validation", "pass": not failures, "object_count": len(objects), "failures": failures, "warnings": []}
