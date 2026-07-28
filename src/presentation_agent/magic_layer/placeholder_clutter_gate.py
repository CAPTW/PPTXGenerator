"""Placeholder clutter policy and gate for Magic Layer D06.1."""

from __future__ import annotations

from typing import Any


def placeholder_clutter_policy_v1() -> dict[str, Any]:
    return {
        "schema_name": "placeholder_clutter_policy_v1",
        "status": "recorded",
        "rules": [
            "Placeholder diamonds are allowed only as integrated semantic icon or slot markers.",
            "Repeated floating diamonds cannot dominate the slide.",
            "Decorative markers must not replace card, panel, table, process, or timeline structure.",
            "Icon placeholders must have semantic role and SVG/vector or PPT shape disposition.",
            "Excess placeholder markers are high product risk when archetype identity is reduced.",
        ],
        "max_floating_placeholder_markers": 6,
        "max_placeholder_marker_area_ratio": 0.035,
        "canva_parity_claimed": False,
    }


def evaluate_placeholder_clutter(spec: dict[str, Any], *, max_markers: int = 6, max_area_ratio: float = 0.035) -> dict[str, Any]:
    objects = spec.get("objects") or []
    markers = [
        obj
        for obj in objects
        if obj.get("placeholder_marker")
        or obj.get("object_type") in {"ppt_vector_shape_icon", "svg_vector"}
        or obj.get("primitive_family") == "icon_region"
    ]
    floating = [obj for obj in markers if not obj.get("integrated_marker")]
    area_ratio = round(sum(_area(obj.get("bbox_norm")) for obj in markers), 5)
    dominates = len(floating) > max_markers or area_ratio > max_area_ratio
    return {
        "schema_name": "placeholder_clutter_report",
        "reference_id": spec.get("reference_id"),
        "status": "passed" if not dominates else "failed",
        "placeholder_marker_count": len(markers),
        "floating_placeholder_marker_count": len(floating),
        "placeholder_marker_area_ratio": area_ratio,
        "max_floating_placeholder_markers": max_markers,
        "max_placeholder_marker_area_ratio": max_area_ratio,
        "dominates_slide": dominates,
        "findings": [
            {
                "issue": "placeholder_diamond_clutter",
                "severity": "HIGH_PRODUCT_RISK",
                "evidence": f"{len(floating)} floating markers, area ratio {area_ratio}",
            }
        ]
        if dominates
        else [],
    }


def _area(bbox: Any) -> float:
    if not bbox or len(bbox) != 4:
        return 0.0
    return max(0.0, float(bbox[2])) * max(0.0, float(bbox[3]))
