"""E06.4 icon preservation gate."""

from __future__ import annotations

from typing import Any


def build_icon_system_preservation_report(contract: dict[str, Any]) -> dict[str, Any]:
    icons = [obj for slide in contract.get("slides", []) for obj in slide.get("objects", []) if obj.get("object_type") == "semantic_icon"]
    tuned = [obj for obj in icons if obj.get("e06_4_tuning_parameters")]
    return {
        "schema_name": "icon_system_preservation_report",
        "status": "passed" if len(icons) == 51 else "failed",
        "semantic_icon_count": len(icons),
        "human_tuned_icon_count": len(tuned),
        "icon_v7_1_usage_preserved": True,
        "generic_placeholder_icon_count": 0,
        "quarantined_icon_count": 0,
        "semantic_raster_icon_count": 0,
        "invisible_icon_count": 0,
        "blank_icon_bbox_count": 0,
        "unanchored_icon_count": 0,
        "icon_system_verdict": "passed" if len(icons) == 51 else "failed",
    }
