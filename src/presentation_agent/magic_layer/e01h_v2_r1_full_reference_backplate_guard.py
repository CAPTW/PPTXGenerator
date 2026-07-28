"""Guard against full-reference/page backplate shortcuts."""

from __future__ import annotations

from typing import Any


def guard_full_reference_backplates(segments: list[dict[str, Any]]) -> dict[str, Any]:
    violations = []
    for segment in segments:
        area = _area(segment.get("bbox_norm", [0, 0, 0, 0]))
        source = str(segment.get("source", segment.get("role", ""))).lower()
        if area >= 0.50 or "reference_page" in source or "full_reference" in source:
            violations.append({"object_id": segment.get("object_id"), "area_ratio": round(area, 3), "source": segment.get("source")})
    return {
        "schema_name": "full_reference_backplate_rejection_report",
        "status": "passed" if not violations else "failed",
        "full_reference_backplate_detected": bool(violations),
        "violation_count": len(violations),
        "violations": violations,
        "canva_parity_claimed": False,
    }


def _area(bbox: list[float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])
