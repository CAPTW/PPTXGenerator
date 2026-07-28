from __future__ import annotations

from typing import Any


RASTER_TARGETS = {"replaceable_image_frame", "bounded_raster", "smart_object_like_image", "raster_image", "bounded_replaceable_image_frame"}


def review_residual_raster_text(
    render_image: str | None = None,
    layers: list[dict[str, Any]] | None = None,
    suppression_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    layers = layers or []
    suppression_evidence = suppression_evidence or []
    limitations: list[str] = []
    if not render_image:
        limitations.append("render image is missing; residual raster text review needs visual evidence")
        return {
            "schema": "residual_raster_text_review.v1",
            "residual_raster_text_risk_status": "INSUFFICIENT_EVIDENCE",
            "risk_regions": [],
            "overlay_items": [],
            "patch_request_suggestions": [],
            "warnings": [],
            "limitations": limitations,
        }
    suppression_by_layer = {item.get("target_layer_id"): item for item in suppression_evidence if item.get("replacement_object_id")}
    risk_regions = []
    overlay_items = []
    patch_suggestions = []
    for layer in layers:
        role = " ".join(str(layer.get(key, "")) for key in ("semantic_role", "layer_category", "name")).lower()
        target = str(layer.get("pptx_target") or layer.get("editability_target") or "")
        layer_id = layer.get("layer_id") or layer.get("id")
        is_semantic_text = any(token in role for token in ("text", "title", "subtitle", "body", "caption", "footer", "source"))
        if is_semantic_text and target in RASTER_TARGETS and layer_id not in suppression_by_layer:
            risk = {"layer_id": layer_id, "bbox_norm": layer.get("bbox_norm"), "reason": "semantic text region targets raster/image field without suppression+replacement evidence"}
            risk_regions.append(risk)
            overlay_items.append(
                {
                    "overlay_item_id": f"residual_raster_{layer_id or len(overlay_items)}",
                    "layer_id": layer_id,
                    "category": "residual_raster_text_risk",
                    "label": layer_id or "residual raster text",
                    "bbox_norm": layer.get("bbox_norm"),
                    "severity": "high",
                    "draw_style": "crosshatch",
                    "message": risk["reason"],
                }
            )
            patch_suggestions.append({"patch_class": "PATCH_RASTER_TEXT_SUPPRESSION", "layer_id": layer_id, "bbox_norm": layer.get("bbox_norm")})
    status = "RISK_DETECTED" if risk_regions else "PASS_BY_LEDGER" if suppression_evidence else "VISUAL_REVIEW_REQUIRED"
    return {
        "schema": "residual_raster_text_review.v1",
        "residual_raster_text_risk_status": status,
        "risk_regions": risk_regions,
        "overlay_items": overlay_items,
        "patch_request_suggestions": patch_suggestions,
        "warnings": [] if status != "VISUAL_REVIEW_REQUIRED" else ["No suppression ledger was provided; visual review remains required."],
        "limitations": limitations,
    }
