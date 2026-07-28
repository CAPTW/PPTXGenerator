from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import bbox_valid, duplicate_ids, is_full_slide_bbox, is_semantic_text, is_structured_semantic


@dataclass
class PsdLikeDocument:
    schema: str
    document_id: str
    source_reference_id: str
    canvas: dict[str, Any]
    layers: list[dict[str, Any]]
    groups: list[dict[str, Any]] = field(default_factory=list)
    global_tokens: dict[str, Any] | None = None
    unknown_policy: str = "fatal_if_content_bearing"
    provenance: dict[str, Any] = field(default_factory=dict)
    validation_summary: dict[str, Any] = field(default_factory=dict)


def validate_psd_like_document(document: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    layers = [layer for layer in document.get("layers", []) if isinstance(layer, dict)]

    for duplicate in sorted(duplicate_ids(layers, "id")):
        failures.append(f"Duplicate layer id: {duplicate}")

    for layer in layers:
        layer_id = str(layer.get("id", "<missing>"))
        bbox = layer.get("bbox_norm")
        if not bbox_valid(bbox):
            failures.append(f"Layer {layer_id} bbox_norm is invalid or out of range.")
        target = str(layer.get("pptx_target", ""))
        kind = str(layer.get("kind", ""))
        if is_full_slide_bbox(bbox) and (kind in {"bounded_raster", "smart_object_like_image", "unknown"} or layer.get("raster_allowed")):
            failures.append(f"Layer {layer_id} is a full-slide raster or unknown plan.")
        if is_semantic_text(layer) and target != "ppt_text_box":
            failures.append(f"Semantic text layer {layer_id} must target ppt_text_box, not {target}.")
        if is_structured_semantic(layer) and target in {"bounded_raster", "replaceable_image_frame", "smart_object_like_image"}:
            failures.append(f"Structured semantic layer {layer_id} cannot target raster fallback {target}.")
        if str(layer.get("kind")) == "unknown" and layer.get("content_bearing"):
            failures.append(f"Unknown content-bearing layer {layer_id} is fatal.")
        if str(layer.get("kind")) == "unknown" and not layer.get("content_bearing"):
            warnings.append(f"Unknown decorative layer {layer_id} requires manual review warning.")

    return {
        "schema_name": "psd_like_layer_model_validation",
        "pass": not failures,
        "layer_count": len(layers),
        "group_count": len(document.get("groups", []) or []),
        "failures": failures,
        "warnings": warnings,
    }
