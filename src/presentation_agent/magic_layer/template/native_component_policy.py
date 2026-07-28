from __future__ import annotations

from typing import Any


NATIVE_COMPONENT_TYPES = [
    "text_box",
    "shape",
    "card_panel",
    "svg_icon",
    "native_chart",
    "editable_shape_chart",
    "native_table",
    "editable_shape_grid_table",
    "editable_timeline",
    "editable_matrix",
    "editable_roadmap",
    "footer_source_strip",
    "replaceable_image_frame",
    "suppression_shape",
]


def native_component_requirement(component_id: str, slot_id: str, component_type: str, required: bool = True) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "slot_id": slot_id,
        "component_type": component_type,
        "required": required,
        "accepted_targets": _accepted_targets(component_type),
        "forbidden_targets": ["raster_image", "bounded_raster", "screenshot_slide"],
        "data_editable_required": component_type in {"native_chart", "editable_shape_chart", "native_table", "editable_shape_grid_table"},
        "text_editable_required": component_type in {"text_box", "native_chart", "editable_shape_chart", "native_table", "editable_shape_grid_table"},
        "style_editable_required": True,
        "validation_rules": [f"validate_{component_type}"],
        "review_hooks": [],
    }


def _accepted_targets(component_type: str) -> list[str]:
    mapping = {
        "native_chart": ["native_chart", "editable_shape_chart"],
        "editable_shape_chart": ["editable_shape_chart", "native_chart"],
        "native_table": ["native_table", "editable_shape_grid_table"],
        "editable_shape_grid_table": ["editable_shape_grid_table", "native_table"],
        "editable_timeline": ["editable_timeline", "ppt_shape_group"],
        "editable_matrix": ["editable_matrix", "ppt_shape_group"],
        "editable_roadmap": ["editable_roadmap", "ppt_shape_group"],
    }
    return mapping.get(component_type, [component_type])


def validate_native_component_requirement(requirement: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if requirement.get("component_type") not in NATIVE_COMPONENT_TYPES:
        failures.append("unknown native component type")
    if requirement.get("required") and "explicit_reject" in requirement.get("accepted_targets", []):
        failures.append("required native component cannot accept explicit_reject as passing target")
    return {"pass": not failures, "failures": failures}
