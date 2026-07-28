"""Icon insertion route policy for E03.4.1."""

from __future__ import annotations

from typing import Any


def build_icon_insertion_route_policy_v2() -> dict[str, Any]:
    return {
        "schema_name": "icon_insertion_route_policy_v2",
        "status": "passed",
        "allowed_routes": [
            "true_svg_media_insertion",
            "native_vector_conversion",
            "ppt_freeform_line_primitive_reconstruction",
        ],
        "selected_default_route": "true_svg_media_insertion",
        "forbidden_routes": [
            "png_jpeg_icon_fallback",
            "invisible_svg_media_counted_as_pass",
            "preview_only_svg_counted_as_pass",
        ],
        "semantic_raster_icon_count": 0,
        "requires_actual_powerpoint_render_visibility": True,
    }
