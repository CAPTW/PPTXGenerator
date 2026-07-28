from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .common import bbox_valid, is_full_slide_bbox


@dataclass
class Selection:
    selection_id: str
    layer_id: str
    bbox_norm: list[float]
    role: str
    selection_source: str
    confidence: float
    content_bearing: bool
    editable_required: bool


@dataclass
class Mask:
    mask_id: str
    kind: str
    bbox_norm: list[float]
    feather: float
    hard_edge: bool


def validate_mask_selection_document(document: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    selections = [item for item in document.get("selections", []) if isinstance(item, dict)]
    masks = [item for item in document.get("masks", []) if isinstance(item, dict)]
    suppressions = [item for item in document.get("suppression_regions", []) if isinstance(item, dict)]

    for selection in selections:
        if not selection.get("selection_id") or not selection.get("layer_id"):
            failures.append("Selection requires selection_id and layer_id.")
        if not bbox_valid(selection.get("bbox_norm")):
            failures.append(f"Selection {selection.get('selection_id')} bbox_norm is invalid.")
    for mask in masks:
        if not mask.get("mask_id"):
            failures.append("Mask requires mask_id.")
        if not bbox_valid(mask.get("bbox_norm")):
            failures.append(f"Mask {mask.get('mask_id')} bbox_norm is invalid.")
        if is_full_slide_bbox(mask.get("bbox_norm")):
            failures.append(f"Full-slide mask {mask.get('mask_id')} is forbidden for product content.")
    for suppression in suppressions:
        if not suppression.get("target_layer_id") or not suppression.get("target_selection_id"):
            failures.append(f"Suppression {suppression.get('suppression_id')} requires target layer and target selection.")
        reason = str(suppression.get("reason", ""))
        if reason.startswith("suppress_raster_text") and not suppression.get("replacement_object_id"):
            failures.append(f"Suppression {suppression.get('suppression_id')} requires editable replacement object.")
        if not bbox_valid(suppression.get("cover_bbox_norm")):
            failures.append(f"Suppression {suppression.get('suppression_id')} cover_bbox_norm is invalid.")
    return {
        "schema_name": "mask_selection_validation",
        "pass": not failures,
        "selection_count": len(selections),
        "mask_count": len(masks),
        "suppression_count": len(suppressions),
        "failures": failures,
        "warnings": warnings,
    }
