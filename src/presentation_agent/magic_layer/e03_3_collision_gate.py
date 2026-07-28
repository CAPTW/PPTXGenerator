"""Semantic object collision gate for E03.3."""

from __future__ import annotations

from typing import Any


def build_object_collision_report(archetype: str, graph: dict[str, Any]) -> dict[str, Any]:
    semantic = [node for node in graph["nodes"] if node.get("content_bearing")]
    collisions = []
    for idx, left in enumerate(semantic):
        for right in semantic[idx + 1 :]:
            if _overlap(left["bbox_norm"], right["bbox_norm"]) and not (_contains(left["bbox_norm"], right["bbox_norm"]) or _contains(right["bbox_norm"], left["bbox_norm"])):
                collisions.append({"a": left["object_id"], "b": right["object_id"]})
    return {"schema_name": "object_collision_report", "status": "passed" if not collisions else "failed", "archetype_id": archetype, "semantic_object_collision_count": len(collisions), "object_collision_count": len(collisions), "collisions": collisions}


def _overlap(a: list[float], b: list[float]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return min(ax1, bx1) > max(ax0, bx0) and min(ay1, by1) > max(ay0, by0)


def _contains(a: list[float], b: list[float]) -> bool:
    return a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]
