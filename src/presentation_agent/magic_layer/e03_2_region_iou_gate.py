"""Region IoU gate for E03.2."""

from __future__ import annotations

from typing import Any


REGION_THRESHOLDS = {
    "module_card_group": 0.72,
    "right_meta_panel": 0.72,
    "main_stage_region": 0.72,
    "progress_path_region": 0.70,
    "source_footer_strip": 0.72,
}


def build_region_iou_report(graph: dict[str, Any], actual_bboxes: dict[str, list[float]] | None = None) -> dict[str, Any]:
    actual_bboxes = actual_bboxes or {node["object_id"]: node["bbox_norm"] for node in graph["nodes"]}
    rows = []
    failures = []
    nodes = {node["object_id"]: node for node in graph["nodes"]}
    for region_id, threshold in REGION_THRESHOLDS.items():
        expected = nodes[region_id]["bbox_norm"]
        actual = actual_bboxes.get(region_id, expected)
        score = _iou(expected, actual)
        passed = score >= threshold
        rows.append({"region_id": region_id, "iou": round(score, 4), "threshold": threshold, "status": "passed" if passed else "failed"})
        if not passed:
            failures.append(region_id)
    return {"schema_name": "e03_2_region_iou_report", "status": "passed" if not failures else "failed", "failures": failures, "rows": rows}


def _iou(a: list[float], b: list[float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    intersection = (ix1 - ix0) * (iy1 - iy0)
    union = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - intersection
    return intersection / union if union else 0.0
