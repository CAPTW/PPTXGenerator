"""Build known source-layer truth for controlled PDFB02 fixtures."""

from __future__ import annotations

from typing import Any


def build_layer_truth(definition: dict[str, Any]) -> dict[str, Any]:
    fixture_id = definition["fixture_id"]
    text = [
        _obj("text_title", "semantic_text", [0.06, 0.06, 0.64, 0.12], "text", 10, "ppt_text"),
        _obj("text_subtitle", "semantic_text", [0.06, 0.13, 0.66, 0.18], "text", 11, "ppt_text"),
        _obj("footer_source", "footer_source", [0.06, 0.88, 0.92, 0.94], "text", 90, "ppt_text"),
    ]
    icons = [_obj("icon_marker_1", "semantic_icon", [0.08, 0.25, 0.12, 0.32], "vector_icon", 30, "svg_or_native_vector")]
    vector = [
        _obj("panel_frame", "card_panel", [0.06, 0.20, 0.92, 0.78], "rect", 20, "ppt_shape"),
        _obj("accent_rule", "connector_vector", [0.08, 0.82, 0.90, 0.83], "line", 80, "ppt_line"),
    ]
    table_chart = []
    if definition.get("requires_chart"):
        table_chart.append(_obj("chart_1", "chart", [0.14, 0.34, 0.56, 0.70], "chart", 40, "native_chart"))
    if definition.get("requires_table"):
        table_chart.append(_obj("table_1", "table", [0.10, 0.25, 0.72, 0.74], "table_grid", 40, "native_table"))
    raster_fields = []
    if definition.get("has_raster_backplate"):
        raster_fields.append(_obj("image_backplate_1", "nonsemantic_visual_backplate", [0.52, 0.18, 0.94, 0.78], "raster_image", 5, "bounded_raster_backplate"))
    backplates = [_obj("background_substrate", "nonsemantic_visual_backplate", [0.00, 0.00, 1.00, 1.00], "background_fill", 1, "ppt_shape_or_texture")]
    truth_objects = backplates + raster_fields + vector + icons + table_chart + text
    return {
        "schema_name": "source_layer_truth",
        "status": "passed",
        "fixture_id": fixture_id,
        "style_family": definition["style_family"],
        "background_mode": definition["background_mode"],
        "semantic_text_objects": text,
        "semantic_icon_objects": icons,
        "table_chart_objects": table_chart,
        "card_panel_objects": [vector[0]],
        "connector_vector_objects": [vector[1]],
        "footer_source_objects": [text[-1]],
        "nonsemantic_visual_backplates": backplates,
        "raster_image_fields": raster_fields,
        "vector_objects": vector + icons,
        "z_order": [obj["object_id"] for obj in sorted(truth_objects, key=lambda row: row["z_order"])],
        "all_objects": truth_objects,
        "allowed_raster_policy": {
            "full_slide_reference_background_allowed": False,
            "allowed_raster_object_ids": [obj["object_id"] for obj in raster_fields + backplates if obj["semantic_role"] == "nonsemantic_visual_backplate"],
            "forbidden_raster_roles": ["semantic_text", "semantic_icon", "chart", "table", "footer_source", "card_panel"],
        },
        "expected_editability_targets": {
            "semantic_text": "ppt_text",
            "semantic_icon": "svg_or_native_vector",
            "chart": "native_chart",
            "table": "native_table",
            "card_panel": "ppt_shape",
            "footer_source": "ppt_text",
        },
        "canva_parity_claimed": False,
    }


def _obj(object_id: str, role: str, bbox: list[float], primitive: str, z: int, target: str) -> dict[str, Any]:
    obj = {
        "object_id": object_id,
        "zone_id": object_id,
        "semantic_role": role,
        "bbox_norm": bbox,
        "primitive_type": primitive,
        "z_order": z,
        "allowed_raster": role == "nonsemantic_visual_backplate",
        "expected_editability_target": target,
    }
    if role in {"semantic_text", "footer_source"}:
        obj["text"] = {
            "text_title": "PDF/PPT-like conversion benchmark",
            "text_subtitle": "Controlled fixture with known object truth",
            "footer_source": "Local PDFB02 benchmark fixture",
        }.get(object_id, object_id.replace("_", " ").title())
    return obj
