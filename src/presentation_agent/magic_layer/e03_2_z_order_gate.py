"""Z-order checks for E03.2."""

from __future__ import annotations

from typing import Any


ORDER_RULES = (
    ("background_base", "dark_header_region"),
    ("background_base", "main_stage_region"),
    ("main_stage_region", "progress_path_region"),
    ("main_stage_region", "module_card_group"),
    ("module_card_group", "module_card_02_active"),
    ("main_stage_region", "right_meta_panel"),
    ("main_stage_region", "reading_path_region"),
    ("main_stage_region", "source_footer_strip"),
)


def build_z_order_ledger(graph: dict[str, Any]) -> dict[str, Any]:
    order = {node["object_id"]: int(node["z_order"]) for node in graph["nodes"]}
    rows = []
    fatal = []
    for below, above in ORDER_RULES:
        passed = order[below] < order[above]
        rows.append({"below": below, "above": above, "below_z": order[below], "above_z": order[above], "status": "passed" if passed else "failed"})
        if not passed:
            fatal.append({"below": below, "above": above})
    return {
        "schema_name": "e03_2_z_order_ledger",
        "status": "passed" if not fatal else "failed",
        "fatal_inversion_count": len(fatal),
        "fatal_inversions": fatal,
        "rows": rows,
    }
