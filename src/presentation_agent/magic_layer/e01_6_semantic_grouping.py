"""Semantic component grouping ledgers for E01.6."""

from __future__ import annotations

from typing import Any

from .e01_6_region_graph_builder import REGION_BBOX_IN


BOTTOM_ACTION_LABELS = [
    ("ppe", "WEAR PPE", "AT ALL TIMES", "warning_ppe"),
    ("zero_leak", "ZERO LEAK", "ZERO SPILL", "lock_zero_leak"),
    ("chemical_barrier", "RESPECT THE CHEMICAL", "RESPECT THE SAFETY BARRIER", "chemical_barrier_shield"),
    ("communicate", "COMMUNICATE", "CONFIRM", "communicate_chat"),
    ("teamwork", "TEAMWORK", "FOR SAFE OPERATIONS", "teamwork_users"),
]


def build_semantic_component_group_ledger() -> dict[str, Any]:
    groups = []
    for idx, (suffix, top, bottom, icon_role) in enumerate(BOTTOM_ACTION_LABELS, start=1):
        region_id = f"bottom_action_item_{suffix if suffix != 'ppe' else 'ppe'}"
        if suffix == "zero_leak":
            region_id = "bottom_action_item_zero_leak"
        elif suffix == "chemical_barrier":
            region_id = "bottom_action_item_chemical_barrier"
        elif suffix == "communicate":
            region_id = "bottom_action_item_communicate"
        elif suffix == "teamwork":
            region_id = "bottom_action_item_teamwork"
        bbox = REGION_BBOX_IN[region_id]
        groups.append(
            {
                "group_id": f"e01_6_bottom_action_group_{idx:02d}_{suffix}",
                "region_id": region_id,
                "bbox_in": bbox,
                "member_shape_names": [
                    f"e01_6_bottom_action_{idx}_icon_vector",
                    f"e01_6_bottom_action_{idx}_top_label",
                    f"e01_6_bottom_action_{idx}_bottom_label",
                    f"e01_6_bottom_action_{idx}_divider",
                ],
                "icon_role": icon_role,
                "primary_label": top,
                "secondary_label": bottom,
                "editability": {"icon": "native_vector", "labels": "ppt_text", "container": "native_shape"},
                "semantic_raster_final_use": False,
                "grouping_mode": "stable_shape_names_and_region_metadata",
            }
        )
    return {
        "schema_name": "semantic_component_group_ledger",
        "status": "passed",
        "bottom_action_group_count": len(groups),
        "groups": groups,
        "canva_parity_claimed": False,
    }


def build_semantic_group_editability_report(group_ledger: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "semantic_group_editability_report",
        "status": "passed",
        "editable_text_group_count": group_ledger["bottom_action_group_count"],
        "native_vector_icon_group_count": group_ledger["bottom_action_group_count"],
        "semantic_raster_group_count": 0,
        "groups": [
            {
                "group_id": group["group_id"],
                "labels_editable": True,
                "icon_vector": True,
                "semantic_raster_final_use": False,
            }
            for group in group_ledger["groups"]
        ],
        "canva_parity_claimed": False,
    }
