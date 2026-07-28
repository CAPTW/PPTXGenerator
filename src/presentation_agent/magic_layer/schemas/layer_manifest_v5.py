from __future__ import annotations

from typing import Any

from .common import bbox_valid, duplicate_ids, is_full_slide_bbox, is_semantic_object


def validate_layer_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    layers = [item for item in manifest.get("layers", []) if isinstance(item, dict)]
    for duplicate in duplicate_ids(layers, "layer_id"):
        failures.append(f"Duplicate manifest layer id: {duplicate}")
    for layer in layers:
        layer_id = layer.get("layer_id", "<missing>")
        if not bbox_valid(layer.get("bbox_norm")):
            failures.append(f"Manifest layer {layer_id} bbox_norm is invalid.")
        if is_semantic_object(layer) and layer.get("raster_allowed"):
            failures.append(f"Manifest semantic layer {layer_id} cannot allow raster.")
        if str(layer.get("semantic_role", "")).lower() == "unknown" and layer.get("content_bearing"):
            failures.append(f"Manifest unknown content-bearing layer {layer_id} is fatal.")
        if is_full_slide_bbox(layer.get("bbox_norm")) and layer.get("raster_allowed"):
            failures.append(f"Manifest layer {layer_id} is full-slide raster.")
    return {"schema_name": "layer_manifest_v5_validation", "pass": not failures, "layer_count": len(layers), "failures": failures, "warnings": []}
