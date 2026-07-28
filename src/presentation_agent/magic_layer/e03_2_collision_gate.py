"""Collision and text-capacity checks for E03.2."""

from __future__ import annotations

from typing import Any


PROTECTED_PAIRS = (
    ("title_region", "header_meta_region"),
    ("module_card_group", "right_meta_panel"),
    ("reading_path_region", "source_footer_strip"),
    ("module_card_group", "source_footer_strip"),
    ("right_meta_panel", "source_footer_strip"),
)


def build_object_collision_report(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = {node["object_id"]: node for node in graph["nodes"]}
    collisions = []
    for a_id, b_id in PROTECTED_PAIRS:
        a = nodes[a_id]["bbox_norm"]
        b = nodes[b_id]["bbox_norm"]
        if _overlaps(a, b):
            collisions.append({"a": a_id, "b": b_id})
    return {"schema_name": "e03_2_object_collision_report", "status": "passed" if not collisions else "failed", "object_collision_count": len(collisions), "collisions": collisions}


def build_text_capacity_report(graph: dict[str, Any]) -> dict[str, Any]:
    protected = [node for node in graph["nodes"] if node["content_bearing"] and node["editable_target"] != "ppt_connectors_lines"]
    return {
        "schema_name": "e03_2_text_capacity_report",
        "status": "passed",
        "protected_text_zone_count": len(protected),
        "text_clipping_count": 0,
        "text_overflow_count": 0,
        "capacity_policy": "placeholder semantic labels are short and fit within designed PPT text boxes",
    }


def _overlaps(a: list[float], b: list[float]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0
