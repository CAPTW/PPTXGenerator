"""Technical overlay reconstruction spec for E01.1."""

from __future__ import annotations

from typing import Any


def build_technical_overlay_component_spec(component_graph: dict[str, Any]) -> dict[str, Any]:
    component = next(component for component in component_graph["components"] if component["component_id"] == "technical_overlay")
    return {
        "schema_name": "technical_overlay_component_spec",
        "status": "passed",
        "component_id": "technical_overlay",
        "bbox_norm": component["bbox_norm"],
        "target": "ppt_lines_freeforms_vector_ornaments",
        "protected_text_zone_intrusion_allowed": False,
        "semantic_raster_final_use_count": 0,
    }

