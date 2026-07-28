"""Audit semantic overlap in visual backplates."""

from __future__ import annotations

from typing import Any


def audit_backplate_semantic_overlap(backplates: list[dict[str, Any]], semantic_zones: list[dict[str, Any]]) -> dict[str, Any]:
    violations = []
    reference_page = False
    for backplate in backplates:
        bbox = backplate.get("bbox_norm", [0, 0, 0, 0])
        area = _area(bbox)
        reference_like = backplate.get("source") == "reference_derived_picture" or "reference" in str(backplate.get("object_id", "")).lower()
        reference_page = reference_page or (reference_like and area >= 0.50)
        for zone in semantic_zones:
            ratio = _overlap_ratio(bbox, zone.get("bbox_norm", [0, 0, 0, 0]))
            if reference_like and ratio > 0.20:
                violations.append(
                    {
                        "backplate_id": backplate.get("object_id") or backplate.get("object_name"),
                        "semantic_object_id": zone.get("object_id") or zone.get("zone_id"),
                        "overlap_ratio": round(ratio, 3),
                    }
                )
                break
    return {
        "schema_name": "visual_backplate_semantic_overlap_report",
        "status": "passed" if not violations else "failed",
        "overlap_violation_count": len(violations),
        "violations": violations,
        "reference_page_raster_backplate_detected": reference_page,
        "backplate_used_to_hide_unresolved_semantic_objects": bool(violations),
        "canva_parity_claimed": False,
    }


def _overlap_ratio(a: list[float], b: list[float]) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    return inter / max(_area(b), 1e-6)


def _area(bbox: list[float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])
