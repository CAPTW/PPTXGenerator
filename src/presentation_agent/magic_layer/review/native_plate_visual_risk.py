from __future__ import annotations

from typing import Any


def review_native_plate_visual_risk(
    render_image: str | None = None,
    layers: list[dict[str, Any]] | None = None,
    suppression_plan: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    layers = layers or []
    suppression_plan = suppression_plan or []
    limitations: list[str] = []
    if not render_image:
        limitations.append("render image is missing; native plate visual risk cannot be visually confirmed")
    plate_regions = []
    overlay_items = []
    for index, item in enumerate(suppression_plan):
        bbox = item.get("cover_bbox_norm") or item.get("bbox_norm")
        risk = item.get("residual_raster_risk", "unknown")
        severity = "warning" if risk in {"none", "low"} else "high"
        plate_regions.append({"suppression_id": item.get("suppression_id"), "bbox_norm": bbox, "risk": risk})
        overlay_items.append(
            {
                "overlay_item_id": f"native_plate_{item.get('suppression_id', index)}",
                "selection_id": item.get("target_selection_id"),
                "layer_id": item.get("target_layer_id"),
                "category": "native_plate_visual_risk",
                "label": "native plate",
                "bbox_norm": bbox,
                "severity": severity,
                "draw_style": "filled_translucent",
                "message": "native plate/cover shape may flatten local visual fidelity",
            }
        )
    if not plate_regions:
        status = "INSUFFICIENT_EVIDENCE" if limitations and layers else "NO_PLATE_RISK"
    elif any(row["risk"] in {"high", "unknown"} for row in plate_regions):
        status = "PLATE_RISK_HIGH"
    elif any(row["risk"] == "medium" for row in plate_regions):
        status = "PLATE_RISK_MEDIUM"
    else:
        status = "PLATE_RISK_LOW"
    return {
        "schema": "native_plate_visual_risk_review.v1",
        "native_plate_visual_risk_status": status,
        "plate_regions": plate_regions,
        "overlay_items": overlay_items,
        "patch_request_suggestions": [{"patch_class": "PATCH_NATIVE_PLATE_STYLE", "bbox_norm": row.get("bbox_norm")} for row in plate_regions if row.get("risk") in {"medium", "high", "unknown"}],
        "warnings": ["Plate risk is review evidence, not automatic product failure."] if plate_regions else [],
        "limitations": limitations,
    }
