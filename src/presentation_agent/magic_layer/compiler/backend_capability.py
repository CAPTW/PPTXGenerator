from __future__ import annotations

from copy import deepcopy
from typing import Any


def default_capability_matrix() -> dict[str, Any]:
    return {
        "schema": "compiler_backend_capability_matrix.v1",
        "backends": [
            _capability("dry_run_only", available=True, supports_native_chart=True, supports_native_table=True),
            _capability("pptxgenjs", available=False, supports_native_chart=True, supports_native_table=False),
            _capability("python_pptx", available=False, supports_native_chart=False, supports_native_table=True),
        ],
    }


def resolve_backend_capability(backend_name: str = "dry_run_only") -> dict[str, Any]:
    for backend in default_capability_matrix()["backends"]:
        if backend["backend_name"] == backend_name:
            return deepcopy(backend)
    capability = _capability(backend_name, available=False)
    capability["limitations"].append("unknown backend")
    return capability


def supports_instruction_type(instruction_type: str, capability: dict[str, Any]) -> bool:
    mapping = {
        "text_box": "supports_text_box",
        "shape": "supports_shapes",
        "group": "supports_groups",
        "freeform_shape": "supports_freeform",
        "svg_icon": "supports_svg",
        "replaceable_image_frame": "supports_picture_crop",
        "native_chart": "supports_native_chart",
        "native_table": "supports_native_table",
        "editable_shape_chart": "supports_editable_shape_chart",
        "editable_shape_grid_table": "supports_editable_shape_grid_table",
        "editable_timeline": "supports_shapes",
        "editable_matrix": "supports_shapes",
        "editable_roadmap": "supports_shapes",
        "suppression_shape": "supports_shapes",
    }
    return bool(capability.get(mapping.get(instruction_type, ""), False))


def _capability(
    backend_name: str,
    *,
    available: bool,
    supports_native_chart: bool = False,
    supports_native_table: bool = False,
) -> dict[str, Any]:
    return {
        "backend_name": backend_name,
        "available": available,
        "supports_slide_size": True,
        "supports_text_box": True,
        "supports_shapes": True,
        "supports_groups": True,
        "supports_freeform": True,
        "supports_svg": True,
        "supports_picture_crop": True,
        "supports_native_chart": supports_native_chart,
        "supports_native_table": supports_native_table,
        "supports_editable_shape_chart": True,
        "supports_editable_shape_grid_table": True,
        "supports_theme_tokens": True,
        "supports_object_names": True,
        "supports_alt_text": True,
        "supports_z_order": True,
        "limitations": [] if available else ["availability not required for C01 dry-run"],
    }
