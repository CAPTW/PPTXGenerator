"""Coordinate diff gates for PPTX/XML coordinates versus layout contract."""

from __future__ import annotations

from typing import Any


def compare_pptx_to_contract(extraction: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    extracted = {obj["object_id"]: obj for slide in extraction.get("slides", []) for obj in slide.get("objects", [])}
    contracted = {obj["object_id"]: obj for slide in contract.get("slides", []) for obj in slide.get("objects", [])}
    failures: list[dict[str, Any]] = []
    diffs: list[dict[str, Any]] = []
    for object_id, obj in contracted.items():
        current = extracted.get(object_id)
        if not current:
            failures.append({"object_id": object_id, "failure": "contract_object_missing_from_pptx"})
            continue
        diff = _bbox_diff_norm(current["bbox_norm"], obj["bbox_norm"])
        threshold = _threshold_for(obj)
        z_order_match = current.get("z_order") == obj.get("z_order")
        row = {
            "object_id": object_id,
            "object_type": obj.get("object_type"),
            "max_bbox_diff_norm": round(diff, 8),
            "threshold": threshold,
            "z_order_match": z_order_match,
        }
        diffs.append(row)
        if diff > threshold:
            failures.append({**row, "failure": "bbox_diff_exceeds_threshold"})
        if obj.get("content_bearing") and not z_order_match:
            failures.append({**row, "failure": "semantic_z_order_mismatch"})
    for object_id in sorted(set(extracted) - set(contracted)):
        current = extracted[object_id]
        if current.get("content_bearing"):
            failures.append({"object_id": object_id, "failure": "object_missing_from_contract"})
    passed = not failures
    return {
        "schema_name": "pptx_vs_contract_coordinate_diff_report",
        "status": "passed" if passed else "failed",
        "pptx_object_count": len(extracted),
        "contract_object_count": len(contracted),
        "coordinate_diff_failure_count": len(failures),
        "z_order_mismatch_count": sum(1 for failure in failures if failure["failure"] == "semantic_z_order_mismatch"),
        "object_missing_from_contract_count": sum(1 for failure in failures if failure["failure"] == "object_missing_from_contract"),
        "contract_object_missing_from_pptx_count": sum(1 for failure in failures if failure["failure"] == "contract_object_missing_from_pptx"),
        "max_bbox_diff_norm": max((row["max_bbox_diff_norm"] for row in diffs), default=0),
        "diffs": diffs[:250],
        "failures": failures,
    }


def _bbox_diff_norm(a: dict[str, float], b: dict[str, float]) -> float:
    return max(abs(float(a[key]) - float(b[key])) for key in ("x", "y", "w", "h"))


def _threshold_for(obj: dict[str, Any]) -> float:
    if obj.get("object_type") == "semantic_icon":
        return 0.003
    if obj.get("object_type") == "source_footer":
        return 0.005
    return 0.005
