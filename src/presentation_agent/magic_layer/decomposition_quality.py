"""Quality scoring for D01 decomposition manifests."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .layer_schema_v4 import bbox_area_ratio


def score_decomposition(layers: list[dict[str, Any]], *, image_width: int, image_height: int) -> dict[str, Any]:
    type_counts = Counter(layer["layer_type"] for layer in layers)
    unknown_layers = [layer for layer in layers if layer["layer_type"] == "unknown"]
    content_unknown = [layer for layer in unknown_layers if layer["content_bearing"]]
    full_crop_violations = [
        layer
        for layer in layers
        if layer.get("crop_path")
        and layer["layer_type"] != "background_base"
        and bbox_area_ratio(layer["bbox_px"], image_width, image_height) > 0.75
    ]
    crop_count = sum(1 for layer in layers if layer.get("crop_path"))
    mask_count = sum(1 for layer in layers if layer.get("mask_path"))
    text_count = sum(1 for layer in layers if layer["layer_type"] in {"title_text_region", "subtitle_text_region", "body_text_region", "source_footer_strip"})
    icon_count = type_counts.get("icon_region", 0)
    chart_table_count = type_counts.get("chart_region", 0) + type_counts.get("table_region", 0) + type_counts.get("matrix_region", 0)
    layer_density_score = min(10.0, len(layers) / 3)
    semantic_coverage_score = min(10.0, len([l for l in layers if l["layer_type"] != "unknown"]) / max(1, len(layers)) * 10)
    crop_score = min(10.0, crop_count / max(1, len(layers) - 1) * 10)
    mask_score = min(10.0, mask_count / max(1, crop_count) * 10)
    unknown_policy_score = 10.0 if not content_unknown else 3.0
    d02_ready = not full_crop_violations and not content_unknown and bool(layers) and crop_count > 0
    score = round((layer_density_score + semantic_coverage_score + crop_score + mask_score + unknown_policy_score) / 5, 2)
    return {
        "schema_name": "decomposition_quality_report",
        "status": "passed_limited_automation" if d02_ready else "blocking_unknowns_or_crop_violations",
        "overall_score": score,
        "scores": {
            "layer_count_density": round(layer_density_score, 2),
            "semantic_region_coverage": round(semantic_coverage_score, 2),
            "crop_quality": round(crop_score, 2),
            "mask_quality": round(mask_score, 2),
            "z_order_confidence": "see_z_order_estimate",
            "unknown_layer_policy": unknown_policy_score,
            "text_region_detection_coverage": min(10, text_count * 2),
            "icon_region_detection_coverage": min(10, icon_count * 2),
            "chart_table_region_detection_coverage": min(10, chart_table_count * 3),
            "footer_source_detection": 10 if type_counts.get("source_footer_strip") else 4,
            "reference_preview_resemblance": "debug_visual_review_required",
            "editability_handoff_readiness": 8 if d02_ready else 3,
        },
        "layer_count": len(layers),
        "layer_type_counts": dict(type_counts),
        "crop_count": crop_count,
        "mask_count": mask_count,
        "unknown_layer_count": len(unknown_layers),
        "content_bearing_unknown_layer_count": len(content_unknown),
        "full_slide_crop_violation_count": len(full_crop_violations),
        "d02_ready": d02_ready,
        "blocking_reasons": [
            *([f"content_bearing_unknown_layers:{len(content_unknown)}"] if content_unknown else []),
            *([f"full_slide_crop_violations:{len(full_crop_violations)}"] if full_crop_violations else []),
        ],
    }
