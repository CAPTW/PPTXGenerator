from __future__ import annotations

from copy import deepcopy
from typing import Any


def resolve_z_order(objects: list[dict[str, Any]]) -> dict[str, Any]:
    items = [deepcopy(item) for item in objects]
    warnings: list[str] = []
    z_values = [item.get("z_order", item.get("z_index", 0)) for item in items]
    if len(z_values) != len(set(str(value) for value in z_values)):
        warnings.append("duplicate z-order values resolved deterministically")
    items.sort(key=lambda item: (int(item.get("z_order", item.get("z_index", 0)) or 0), str(item.get("object_id") or item.get("instruction_id") or "")))
    index = {item.get("object_id"): item for item in items if item.get("object_id")}
    for item in items:
        if item.get("pptx_object_type") == "suppression_shape":
            suppressed = index.get(item.get("suppresses_object_id"))
            replacement = index.get(item.get("replacement_editable_object_id"))
            if suppressed and replacement:
                item["_force_between"] = True
                item["z_order"] = int(suppressed.get("z_order", suppressed.get("z_index", 0)) or 0) + 1
                replacement["z_order"] = max(int(replacement.get("z_order", replacement.get("z_index", 0)) or 0), int(item["z_order"]) + 1)
    items.sort(key=lambda item: (int(item.get("z_order", item.get("z_index", 0)) or 0), str(item.get("object_id") or item.get("instruction_id") or "")))
    for resolved, item in enumerate(items, start=1):
        item["resolved_z_order"] = resolved
    return {
        "schema": "z_order_resolution.v1",
        "pass": True,
        "ordered_objects": items,
        "warnings": warnings,
    }
