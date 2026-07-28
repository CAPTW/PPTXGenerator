from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.presentation_agent.magic_layer.planning.geometry_resolver import object_bbox
from src.presentation_agent.magic_layer.schemas.common import is_full_slide_bbox, is_semantic_object


TYPE_MAP = {
    "text_box": ("text_box", "p:sp with a:t text"),
    "shape": ("shape", "p:sp"),
    "group": ("group", "p:grpSp"),
    "freeform_shape": ("freeform", "p:sp custom geometry"),
    "svg_icon": ("svg_icon", "vector/SVG embedding or editable shape approximation"),
    "native_chart": ("native_chart", "c:chart relationship"),
    "native_table": ("native_table", "a:tbl"),
    "editable_shape_chart": ("editable_shape_chart_group", "p:grpSp editable chart approximation"),
    "editable_shape_grid_table": ("editable_shape_grid_table_group", "p:grpSp editable table grid"),
    "editable_timeline": ("editable_timeline_group", "p:grpSp editable timeline"),
    "editable_matrix": ("editable_matrix_group", "p:grpSp editable matrix"),
    "editable_roadmap": ("editable_roadmap_group", "p:grpSp editable roadmap"),
    "replaceable_image_frame": ("replaceable_image_frame", "p:pic bounded nonsemantic"),
    "suppression_shape": ("suppression_shape", "p:sp native suppression shape"),
}


def map_instruction_to_primitive(instruction: dict[str, Any], backend_name: str = "dry_run_only") -> dict[str, Any]:
    data = deepcopy(instruction)
    instruction_type = str(data.get("pptx_object_type", ""))
    primitive_type, signature = TYPE_MAP.get(instruction_type, ("unsupported", "unsupported"))
    return {
        "primitive_id": f"prim_{data.get('instruction_id', data.get('object_id', 'instruction'))}",
        "source_instruction_id": data.get("instruction_id"),
        "source_object_id": data.get("object_id"),
        "source_slot_id": data.get("slot_id"),
        "primitive_type": primitive_type,
        "geometry": data.get("geometry", {}),
        "style": data.get("style", {}),
        "text": data.get("text"),
        "data": data.get("data"),
        "asset_ref": data.get("asset_ref"),
        "z_order": data.get("z_order", 0),
        "object_name": data.get("object_name"),
        "semantic_role": data.get("semantic_role", ""),
        "editable_required": bool(data.get("editable_required", True)),
        "raster_allowed": bool(data.get("raster_allowed", False)),
        "editability_contract": {
            "editable_required": bool(data.get("editable_required", True)),
            "text_editable": instruction_type == "text_box" or bool(data.get("targetability", {}).get("text_editable")),
            "style_editable": True,
        },
        "validation_checks": data.get("validation_checks", []),
        "expected_ooxml_signature": signature,
        "backend_mapping": backend_name,
        "limitations": [] if primitive_type != "unsupported" else [f"unsupported instruction type {instruction_type}"],
    }


def validate_primitive(primitive: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    ident = primitive.get("primitive_id", "primitive")
    if not primitive.get("source_instruction_id") or not primitive.get("source_object_id"):
        failures.append(f"{ident}: source instruction/object link required")
    if primitive.get("primitive_type") == "unsupported":
        failures.append(f"{ident}: unsupported primitive")
    if primitive.get("semantic_raster") or (primitive.get("raster_allowed") and is_semantic_object(primitive)):
        failures.append(f"{ident}: semantic raster primitive forbidden")
    if primitive.get("primitive_type") in {"full_slide_raster", "screenshot_slide"}:
        failures.append(f"{ident}: full-slide raster/screenshot primitive forbidden")
    if primitive.get("primitive_type") == "replaceable_image_frame" and is_full_slide_bbox(object_bbox(primitive)):
        failures.append(f"{ident}: full-slide image primitive forbidden")
    if primitive.get("editable_required") and not primitive.get("object_name"):
        failures.append(f"{ident}: required semantic primitive missing object_name")
    if primitive.get("editable_required") and not primitive.get("expected_ooxml_signature"):
        failures.append(f"{ident}: required semantic primitive missing expected OOXML signature")
    return {"schema": "pptx_primitive_validation.v1", "pass": not failures, "failures": failures, "primitive": primitive}
