"""Group low-value decorative D01/D03 micro-layers for D05.1."""

from __future__ import annotations

from typing import Any


def decorative_layer_grouping_policy() -> dict[str, Any]:
    return {
        "schema_name": "decorative_layer_grouping_policy_v1",
        "problem": "Rendering every tiny detected layer as an isolated object produces sparse/debug-like slides.",
        "rules": {
            "group_technical_overlays_into_motif_groups": True,
            "suppress_low_confidence_micro_layers": True,
            "content_bearing_layers_must_not_be_hidden": True,
            "semantic_icons_labels_charts_tables_remain_separate": True,
            "grouped_layer_ids_must_be_recorded": True,
        },
        "micro_layer_area_threshold": 0.003,
    }


def group_decorative_layers(reference_id: str, primitive_mapping: dict[str, Any]) -> dict[str, Any]:
    primitives = primitive_mapping.get("primitive_mappings") or []
    groups: dict[str, list[dict[str, Any]]] = {"top": [], "middle": [], "bottom": []}
    suppressed = []
    preserved = []
    for primitive in primitives:
        family = primitive.get("primitive_family")
        area = _area(primitive.get("bbox_norm"))
        semantic = primitive.get("semantic_role")
        if _is_semantic_primitive(family, semantic):
            preserved.append(primitive)
            continue
        if family in {"technical_overlay", "accent_line", "connector_line"}:
            if area < 0.003:
                suppressed.append(_summary(primitive, "grouped_or_suppressed_micro_decorative"))
            else:
                key = _band(primitive.get("bbox_norm"))
                groups[key].append(primitive)
            continue
        if area < 0.002 and family not in {"card_panel", "source_footer_strip"}:
            suppressed.append(_summary(primitive, "suppressed_low_value_micro_layer"))
        else:
            preserved.append(primitive)
    group_objects = []
    for band, items in groups.items():
        if not items:
            continue
        group_objects.append(_group_object(reference_id, band, items))
    return {
        "schema_name": "decorative_layer_grouping",
        "reference_id": reference_id,
        "status": "passed",
        "preserved_primitive_count": len(preserved),
        "grouped_object_count": len(group_objects),
        "suppressed_micro_layer_count": len(suppressed),
        "preserved_primitives": preserved,
        "decorative_group_objects": group_objects,
        "suppressed_layers": suppressed,
    }


def validate_decorative_grouping(grouping: dict[str, Any], content_bearing_layer_ids: set[str]) -> list[str]:
    errors: list[str] = []
    suppressed_ids = {layer_id for item in grouping.get("suppressed_layers") or [] for layer_id in item.get("source_layer_ids") or []}
    hidden_content = sorted(suppressed_ids.intersection(content_bearing_layer_ids))
    if hidden_content:
        errors.append(f"content_bearing_layers_hidden:{','.join(hidden_content)}")
    for item in grouping.get("decorative_group_objects") or []:
        if item.get("semantic_component") != "decorative_overlay_group":
            errors.append(f"invalid_decorative_group_component:{item.get('object_id')}")
    return errors


def _group_object(reference_id: str, band: str, primitives: list[dict[str, Any]]) -> dict[str, Any]:
    boxes = [item.get("bbox_norm") for item in primitives if isinstance(item.get("bbox_norm"), list)]
    x1 = min(float(box[0]) for box in boxes)
    y1 = min(float(box[1]) for box in boxes)
    x2 = max(float(box[0]) + float(box[2]) for box in boxes)
    y2 = max(float(box[1]) + float(box[3]) for box in boxes)
    return {
        "object_id": f"{reference_id}_decorative_{band}_motif_group",
        "object_type": "ppt_shape",
        "primitive_family": "technical_overlay_group",
        "semantic_component": "decorative_overlay_group",
        "major_region_type": "technical_overlay_group",
        "bbox_norm": [round(x1, 6), round(y1, 6), round(x2 - x1, 6), round(y2 - y1, 6)],
        "source_layer_ids": [layer_id for item in primitives for layer_id in item.get("source_layer_ids") or []],
        "z_order": 110,
        "fill": "#00000000",
        "line": "#38BDF8",
        "final_use": "ppt_shape",
        "editable": True,
        "grouped_layer_count": len(primitives),
    }


def _is_semantic_primitive(family: str | None, semantic: str | None) -> bool:
    if family in {"table_region", "matrix_region", "chart_region", "source_footer_strip"}:
        return True
    if semantic in {"source_footer", "title", "body", "chart", "table"}:
        return True
    return False


def _area(bbox_norm: Any) -> float:
    if not isinstance(bbox_norm, list) or len(bbox_norm) != 4:
        return 0.0
    return float(bbox_norm[2]) * float(bbox_norm[3])


def _band(bbox_norm: Any) -> str:
    if not isinstance(bbox_norm, list) or len(bbox_norm) != 4:
        return "middle"
    y_mid = float(bbox_norm[1]) + float(bbox_norm[3]) / 2
    if y_mid < 0.3:
        return "top"
    if y_mid > 0.7:
        return "bottom"
    return "middle"


def _summary(primitive: dict[str, Any], disposition: str) -> dict[str, Any]:
    return {
        "primitive_id": primitive.get("primitive_id"),
        "source_layer_ids": primitive.get("source_layer_ids") or [],
        "primitive_family": primitive.get("primitive_family"),
        "bbox_norm": primitive.get("bbox_norm"),
        "disposition": disposition,
        "content_bearing": False,
    }

