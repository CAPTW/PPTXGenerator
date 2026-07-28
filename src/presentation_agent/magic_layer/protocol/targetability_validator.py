from __future__ import annotations

from typing import Any

from ..schemas.common import is_full_slide_bbox


def validate_targetability(object_graph: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    per_object = []
    for obj in object_graph.get("objects", []) or []:
        obj_id = obj.get("object_id", "<unknown>")
        targetability = obj.get("targetability") or {}
        kind = str(obj.get("object_kind") or "")
        target = str(obj.get("pptx_target") or "")
        object_failures: list[str] = []
        if is_full_slide_bbox(obj.get("bbox_norm")) and target in {"bounded_raster", "raster_image", "smart_object_like_image"}:
            object_failures.append("full-slide raster cannot satisfy targetability")
        if kind == "text" and obj.get("editable_required") and not targetability.get("text_editable"):
            object_failures.append("text_editable required for semantic text")
        if kind in {"chart", "table", "timeline", "matrix", "roadmap"} and not (targetability.get("data_editable") or targetability.get("text_editable")):
            object_failures.append("data_editable or text_editable required for structured semantic object")
        if target == "replaceable_image_frame" and not (targetability.get("replaceable") and targetability.get("crop_editable")):
            object_failures.append("replaceable image frame requires replaceable and crop_editable")
        if kind in {"footer_source", "shape", "suppression_shape"} and obj.get("editable_required") and not (targetability.get("style_editable") or targetability.get("geometry_editable")):
            warnings.append(f"Object {obj_id} has limited style/geometry targetability evidence.")
        failures.extend(f"Object {obj_id}: {failure}" for failure in object_failures)
        per_object.append({"object_id": obj_id, "pass": not object_failures, "failures": object_failures})
    return {
        "schema_name": "targetability_validation",
        "targetability_pass": not failures,
        "per_object_targetability": per_object,
        "failures": failures,
        "warnings": warnings,
    }
