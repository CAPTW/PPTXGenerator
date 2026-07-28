"""Batch z-order gate for E03.3."""

from __future__ import annotations

from typing import Any


def build_z_order_ledger(archetype: str, graph: dict[str, Any]) -> dict[str, Any]:
    order = {node["object_id"]: int(node["z_order"]) for node in graph["nodes"]}
    rules = [(below, above) for below in ("background_base",) for above in order if above != "background_base"]
    rows = []
    fatal = []
    for below, above in rules:
        passed = order.get(below, 0) < order.get(above, 0)
        rows.append({"below": below, "above": above, "below_z": order.get(below), "above_z": order.get(above), "status": "passed" if passed else "failed"})
        if not passed:
            fatal.append({"below": below, "above": above})
    return {"schema_name": "z_order_ledger", "status": "passed" if not fatal else "failed", "archetype_id": archetype, "fatal_inversion_count": len(fatal), "fatal_inversions": fatal, "rows": rows}
