"""Source/footer reconstruction spec for E01.1."""

from __future__ import annotations

from typing import Any


def build_source_footer_component_spec(component_graph: dict[str, Any]) -> dict[str, Any]:
    component = next(component for component in component_graph["components"] if component["component_id"] == "source_footer_strip")
    return {
        "schema_name": "source_footer_component_spec",
        "status": "passed",
        "component_id": "source_footer_strip",
        "bbox_norm": component["bbox_norm"],
        "container_target": "ppt_line_and_shape",
        "text_target": "ppt_text_box",
        "semantic_raster_final_use_count": 0,
    }

