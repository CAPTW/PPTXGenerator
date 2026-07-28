from __future__ import annotations

from typing import Any

from ..schemas.common import bbox_valid, duplicate_ids, is_full_slide_bbox, is_raster_target, is_semantic_object


def validate_graph_consistency(
    psd_like_layer_model: dict[str, Any],
    object_graph: dict[str, Any],
    layer_manifest: dict[str, Any],
    semantic_slot_graph: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    layers = [item for item in psd_like_layer_model.get("layers", []) or [] if isinstance(item, dict)]
    objects = [item for item in object_graph.get("objects", []) or [] if isinstance(item, dict)]
    manifest_layers = [item for item in layer_manifest.get("layers", []) or [] if isinstance(item, dict)]
    slots = [item for item in semantic_slot_graph.get("slots", []) or [] if isinstance(item, dict)]
    layer_ids = {str(layer.get("id")) for layer in layers if layer.get("id")}
    object_ids = {str(obj.get("object_id")) for obj in objects if obj.get("object_id")}
    object_layer_ids = {str(obj.get("layer_id")) for obj in objects if obj.get("layer_id")}
    orphan_content_layers = [layer for layer in layers if layer.get("content_bearing") and str(layer.get("id")) not in object_layer_ids]

    for duplicate in duplicate_ids(layers, "id"):
        errors.append(f"Duplicate layer id: {duplicate}")
    for duplicate in duplicate_ids(objects, "object_id"):
        errors.append(f"Duplicate object id: {duplicate}")
    for duplicate in duplicate_ids(slots, "slot_id"):
        errors.append(f"Duplicate slot id: {duplicate}")

    z_seen: set[int] = set()
    for layer in layers:
        layer_id = str(layer.get("id", "<missing>"))
        z = layer.get("z_index")
        if isinstance(z, int):
            if z in z_seen:
                warnings.append(f"Duplicate z-order {z} requires deterministic resolution.")
            z_seen.add(z)
        if not bbox_valid(layer.get("bbox_norm")):
            errors.append(f"Layer {layer_id} bbox_norm is invalid.")
        if is_full_slide_bbox(layer.get("bbox_norm")) and layer.get("raster_allowed"):
            errors.append(f"Layer {layer_id} is full-slide raster.")
    for layer in orphan_content_layers:
        errors.append(f"Content-bearing layer {layer.get('id')} has no mapped object.")
    for obj in objects:
        obj_id = str(obj.get("object_id", "<missing>"))
        for source_layer_id in obj.get("source_layer_ids") or [obj.get("layer_id")]:
            if source_layer_id and str(source_layer_id) not in layer_ids:
                errors.append(f"Object {obj_id} references missing source layer {source_layer_id}.")
        if obj.get("editable_required") and str(obj.get("pptx_target") or "") in {"", "bounded_raster", "raster_image"}:
            errors.append(f"Editable object {obj_id} lacks PPT-native target.")
        if str(obj.get("object_kind")) == "unknown" and obj.get("content_bearing"):
            errors.append(f"Unknown content-bearing object {obj_id} is fatal.")
        if is_semantic_object(obj) and is_raster_target(str(obj.get("pptx_target") or "")):
            errors.append(f"Semantic object {obj_id} cannot allow raster target.")
        if not bbox_valid(obj.get("bbox_norm")):
            errors.append(f"Object {obj_id} bbox_norm is invalid.")
    for slot in slots:
        slot_id = str(slot.get("slot_id", "<missing>"))
        if slot.get("required") and not slot.get("object_ids"):
            errors.append(f"Required slot {slot_id} has no object.")
        for object_id in slot.get("object_ids") or []:
            if str(object_id) not in object_ids:
                errors.append(f"Slot {slot_id} references missing object {object_id}.")
        if slot.get("required") and slot.get("slot_type") in {"chart", "table", "timeline", "matrix", "roadmap"} and str(slot.get("native_target")) in {"", "bounded_raster", "replaceable_image_frame"}:
            errors.append(f"Required structured slot {slot_id} lacks native/editable target.")
    manifest_object_ids = {str(item.get("object_id")) for item in manifest_layers if item.get("object_id")}
    for obj in objects:
        if obj.get("object_id") and str(obj.get("object_id")) not in manifest_object_ids and manifest_layers:
            warnings.append(f"Object {obj.get('object_id')} is not projected into layer manifest.")
    return {
        "schema_name": "graph_consistency_validation",
        "graph_consistency_pass": not errors,
        "errors": errors,
        "warnings": warnings,
        "object_count": len(objects),
        "layer_count": len(layers),
        "slot_count": len(slots),
        "orphan_counts": {"content_bearing_layers_without_object": len(orphan_content_layers)},
        "fatal_counts": {"errors": len(errors)},
    }
