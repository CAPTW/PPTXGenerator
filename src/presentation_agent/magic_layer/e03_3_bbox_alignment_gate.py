"""Batch bbox alignment gate for E03.3."""

from __future__ import annotations

from typing import Any


def build_bbox_alignment_ledger(archetype: str, graph: dict[str, Any], policy: dict[str, Any], actual_bboxes: dict[str, list[float]] | None = None) -> dict[str, Any]:
    actual_bboxes = actual_bboxes or {node["object_id"]: node["bbox_norm"] for node in graph["nodes"]}
    rows = []
    failures = []
    for node in graph["nodes"]:
        if not node.get("must_preserve"):
            continue
        expected = node["bbox_norm"]
        actual = actual_bboxes.get(node["object_id"], expected)
        threshold = _threshold(node["object_id"], policy)
        drift = max(abs(float(e) - float(a)) for e, a in zip(expected, actual))
        status = "passed" if drift <= threshold else "failed"
        rows.append({"object_id": node["object_id"], "expected_bbox_norm": expected, "actual_bbox_norm": actual, "max_norm_drift": round(drift, 4), "threshold": threshold, "status": status})
        if status == "failed":
            failures.append(node["object_id"])
    return {"schema_name": "bbox_alignment_ledger", "status": "passed" if not failures else "failed", "archetype_id": archetype, "failure_count": len(failures), "failures": failures, "rows": rows}


def _threshold(object_id: str, policy: dict[str, Any]) -> float:
    thresholds = policy["thresholds"]
    if object_id == "title_header_region":
        return thresholds["title_header_region_drift"]
    if object_id == "footer_source_region":
        return thresholds["footer_source_region_drift"]
    if object_id == "side_rail_meta_region":
        return thresholds["side_rail_meta_region_drift"]
    return 0.06
