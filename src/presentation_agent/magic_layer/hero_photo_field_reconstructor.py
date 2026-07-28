"""Hero photo field reconstruction spec for E01.1."""

from __future__ import annotations

from typing import Any


def build_hero_photo_field_component_spec(component_graph: dict[str, Any]) -> dict[str, Any]:
    component = next(component for component in component_graph["components"] if component["component_id"] == "hero_photo_field")
    return {
        "schema_name": "hero_photo_field_component_spec",
        "status": "passed",
        "component_id": "hero_photo_field",
        "bbox_norm": component["bbox_norm"],
        "image_policy": "bounded_replaceable_photo_field",
        "full_slide_background": False,
        "native_overlay_policy": "technical overlays reconstructed as PPT vector lines where feasible",
        "semantic_raster_final_use_count": 0,
    }

