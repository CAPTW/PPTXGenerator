"""Thumbnail callout reconstruction spec for E01.1."""

from __future__ import annotations

from typing import Any


def build_thumbnail_callout_component_spec(component_graph: dict[str, Any]) -> dict[str, Any]:
    component = next(component for component in component_graph["components"] if component["component_id"] == "thumbnail_callout_cluster")
    return {
        "schema_name": "thumbnail_callout_component_spec",
        "status": "passed" if len(component["callouts"]) == 3 else "failed",
        "component_id": "thumbnail_callout_cluster",
        "callout_count": len(component["callouts"]),
        "callouts": [
            {
                "callout_id": f"thumbnail_callout_{item['index']}",
                "role": item["role"],
                "caption": item["label"],
                "image_target": "bounded_replaceable_image_frame",
                "caption_target": "ppt_text_box",
            }
            for item in component["callouts"]
        ],
    }

