"""Z-order repair ledger for E01.6 semantic groups."""

from __future__ import annotations

from typing import Any


def build_object_z_order_repair_ledger() -> dict[str, Any]:
    return {
        "schema_name": "object_z_order_repair_ledger",
        "status": "passed",
        "repair_strategy": "append_rebuilt_bottom_action_bar_after_old_component_removal_so_semantic_text_and_icons_are_above_decorative_bar",
        "semantic_text_above_decorative_layers": True,
        "semantic_icons_above_decorative_layers": True,
        "source_footer_above_bottom_container": True,
        "repairs": [
            {"region_id": "bottom_action_bar", "action": "removed_old_loose_bottom_shapes"},
            {"region_id": "bottom_action_bar", "action": "inserted_container_first_then_dividers_icons_text"},
            {"region_id": "source_footer_strip", "action": "inserted_footer_after_bottom_bar_to_keep_readable"},
        ],
        "canva_parity_claimed": False,
    }
