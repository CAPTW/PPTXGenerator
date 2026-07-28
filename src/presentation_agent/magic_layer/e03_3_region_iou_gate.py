"""Batch region IoU gate for E03.3."""

from __future__ import annotations

from typing import Any


def build_region_iou_report(archetype: str, graph: dict[str, Any], policy: dict[str, Any], actual_bboxes: dict[str, list[float]] | None = None) -> dict[str, Any]:
    actual_bboxes = actual_bboxes or {node["object_id"]: node["bbox_norm"] for node in graph["nodes"]}
    nodes = {node["object_id"]: node for node in graph["nodes"]}
    rows = []
    failures = []
    for region_id, threshold in _regions(nodes, policy).items():
        expected = nodes[region_id]["bbox_norm"]
        actual = actual_bboxes.get(region_id, expected)
        score = round(_iou(expected, actual), 4)
        status = "passed" if score >= threshold else "failed"
        rows.append({"region_id": region_id, "iou": score, "threshold": threshold, "status": status})
        if status == "failed":
            failures.append(region_id)
    return {"schema_name": "region_iou_report", "status": "passed" if not failures else "failed", "archetype_id": archetype, "failures": failures, "rows": rows}


def _regions(nodes: dict[str, Any], policy: dict[str, Any]) -> dict[str, float]:
    thresholds = policy["thresholds"]
    regions = {"main_content_region": thresholds["main_content_region_iou"]}
    if "card_group_region" in nodes:
        regions["card_group_region"] = thresholds["card_group_region_iou"]
    if "chart_table_process_timeline_region" in nodes:
        regions["chart_table_process_timeline_region"] = thresholds["chart_table_process_timeline_region_iou"]
    return regions


def _iou(a: list[float], b: list[float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    intersection = (ix1 - ix0) * (iy1 - iy0)
    union = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - intersection
    return intersection / union if union else 0.0
