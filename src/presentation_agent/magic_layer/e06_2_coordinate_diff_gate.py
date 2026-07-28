"""Coordinate diff gate for contract-first recompiled PPTX."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e06_2_contract_object_factory import parse_contract_shape_name


def normalize_recompiled_extraction(extraction: dict[str, Any]) -> dict[str, Any]:
    slides: list[dict[str, Any]] = []
    for slide in extraction.get("slides", []):
        objects = []
        for obj in slide.get("objects", []):
            parsed = parse_contract_shape_name(obj.get("name", ""))
            if parsed:
                obj = {**obj, **parsed}
            objects.append(obj)
        slides.append({**slide, "objects": objects})
    semantic_icon_count = sum(1 for slide in slides for obj in slide["objects"] if obj.get("contract_object_type") == "semantic_icon")
    return {**extraction, "schema_name": "contract_recompiled_pptx_coordinate_extraction_report", "slides": slides, "semantic_icon_count": semantic_icon_count}


def compare_contract_to_recompiled_pptx(contract: dict[str, Any], extraction: dict[str, Any]) -> dict[str, Any]:
    contract_objects = {obj["object_id"]: obj for slide in contract.get("slides", []) for obj in slide.get("objects", [])}
    extracted_objects = {
        obj["contract_object_id"]: obj
        for slide in extraction.get("slides", [])
        for obj in slide.get("objects", [])
        if obj.get("contract_object_id")
    }
    failures: list[dict[str, Any]] = []
    diffs: list[dict[str, Any]] = []
    for object_id, contract_obj in contract_objects.items():
        current = extracted_objects.get(object_id)
        if not current:
            failures.append({"contract_object_id": object_id, "failure": "missing_contract_object"})
            continue
        diff = _bbox_diff(contract_obj["bbox_norm"], current["bbox_norm"])
        threshold = _threshold(contract_obj)
        z_match = int(contract_obj.get("z_order", -1)) == int(current.get("z_order", -2))
        row = {
            "contract_object_id": object_id,
            "object_type": contract_obj.get("object_type"),
            "bbox_diff_norm": round(diff, 8),
            "threshold": threshold,
            "z_order_match": z_match,
        }
        diffs.append(row)
        if diff > threshold:
            failures.append({**row, "failure": "coordinate_diff_exceeds_threshold"})
        if contract_obj.get("content_bearing") and not z_match:
            failures.append({**row, "failure": "semantic_z_order_diff"})
    extra_semantic = [
        obj
        for slide in extraction.get("slides", [])
        for obj in slide.get("objects", [])
        if obj.get("content_bearing") and not obj.get("contract_object_id") and not str(obj.get("name", "")).startswith("contract_grid::")
    ]
    for obj in extra_semantic:
        failures.append({"object_name": obj.get("name"), "failure": "extra_unrecorded_semantic_object"})
    return {
        "schema_name": "contract_vs_recompiled_pptx_diff_report",
        "status": "passed" if not failures else "failed",
        "contract_object_count": len(contract_objects),
        "recompiled_contract_mapped_object_count": len(extracted_objects),
        "missing_contract_object_count": sum(1 for failure in failures if failure["failure"] == "missing_contract_object"),
        "extra_unrecorded_semantic_object_count": sum(1 for failure in failures if failure["failure"] == "extra_unrecorded_semantic_object"),
        "coordinate_diff_failure_count": sum(1 for failure in failures if failure["failure"] == "coordinate_diff_exceeds_threshold"),
        "z_order_diff_failure_count": sum(1 for failure in failures if failure["failure"] == "semantic_z_order_diff"),
        "max_bbox_diff_norm": max((row["bbox_diff_norm"] for row in diffs), default=0),
        "diffs": diffs[:250],
        "failures": failures,
    }


def _bbox_diff(a: dict[str, float], b: dict[str, float]) -> float:
    return max(abs(float(a[k]) - float(b[k])) for k in ("x", "y", "w", "h"))


def _threshold(obj: dict[str, Any]) -> float:
    if obj.get("object_type") == "semantic_icon":
        return 0.003
    return 0.005
