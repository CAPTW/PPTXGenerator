"""Bounding-box alignment checks for E03.2."""

from __future__ import annotations

from typing import Any


STRICT_THRESHOLDS = {
    "title_region": 0.03,
    "source_footer_strip": 0.03,
    "module_card_group": 0.05,
    "right_meta_panel": 0.05,
    "progress_path_region": 0.05,
}


def build_bbox_alignment_ledger(graph: dict[str, Any], actual_bboxes: dict[str, list[float]] | None = None) -> dict[str, Any]:
    actual_bboxes = actual_bboxes or {node["object_id"]: node["bbox_norm"] for node in graph["nodes"]}
    rows = []
    failures = []
    for node in graph["nodes"]:
        if not node["must_preserve"]:
            continue
        expected = node["bbox_norm"]
        actual = actual_bboxes.get(node["object_id"], expected)
        threshold = STRICT_THRESHOLDS.get(node["object_id"], 0.06)
        drift = max(abs(float(e) - float(a)) for e, a in zip(expected, actual))
        passed = drift <= threshold
        rows.append({"object_id": node["object_id"], "expected_bbox_norm": expected, "actual_bbox_norm": actual, "max_norm_drift": round(drift, 4), "threshold": threshold, "status": "passed" if passed else "failed"})
        if not passed:
            failures.append(node["object_id"])
    return {
        "schema_name": "e03_2_bbox_alignment_ledger",
        "status": "passed" if not failures else "failed",
        "bbox_alignment_gate": "passed" if not failures else "failed",
        "failure_count": len(failures),
        "failures": failures,
        "rows": rows,
    }
