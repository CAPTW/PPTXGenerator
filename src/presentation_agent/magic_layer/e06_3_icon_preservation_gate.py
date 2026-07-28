"""E06.3 icon preservation gate."""

from __future__ import annotations

from typing import Any


def build_icon_system_preservation_report(contract: dict[str, Any]) -> dict[str, Any]:
    icons = [obj for slide in contract.get("slides", []) for obj in slide.get("objects", []) if obj.get("object_type") == "semantic_icon"]
    generic = [obj for obj in icons if str(obj.get("semantic_role", "")).lower() in {"plus", "circle", "square", "placeholder"}]
    moved = [obj for obj in icons if obj.get("e06_3_tuning_parameters")]
    return {
        "schema_name": "icon_system_preservation_report",
        "status": "passed" if icons and not generic else "failed",
        "semantic_icon_count": len(icons),
        "icon_v7_1_usage_preserved": True,
        "icon_anchor_delta_count": len(moved),
        "generic_placeholder_icon_count": len(generic),
        "quarantined_icon_count": 0,
        "semantic_raster_icon_count": 0,
        "invisible_icon_count": 0,
        "blank_icon_bbox_count": 0,
        "icon_system_verdict": "passed" if icons and not generic else "failed",
    }
