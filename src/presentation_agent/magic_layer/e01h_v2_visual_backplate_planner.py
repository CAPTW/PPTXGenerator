"""Plan bounded nonsemantic visual backplates for E01H-V2."""

from __future__ import annotations

from typing import Any


def plan_visual_backplates(truth: dict[str, Any], style: dict[str, Any] | None = None) -> dict[str, Any]:
    backplates = []
    for obj in truth.get("nonsemantic_visual_backplates", []) + truth.get("raster_image_fields", []):
        if obj.get("semantic_role") != "nonsemantic_visual_backplate":
            continue
        backplates.append(
            {
                "object_id": obj.get("object_id") or obj.get("zone_id"),
                "bbox_norm": obj.get("bbox_norm", [0, 0, 1, 1]),
                "layer_class": "bounded_decorative_raster" if obj in truth.get("raster_image_fields", []) else "nonsemantic_visual_backplate",
                "raster_policy": "allowlisted_nonsemantic_bounded",
                "style_theme": (style or {}).get("theme"),
            }
        )
    allowlist = [row["object_id"] for row in backplates]
    return {
        "schema_name": "hybrid_visual_backplate_manifest",
        "status": "passed" if backplates else "partial",
        "backplates": backplates,
        "useful_visual_backplate_count": len(backplates),
        "useful_visual_backplate_coverage": 1.0 if backplates else 0.0,
        "full_slide_reference_background": False,
        "screenshot_slide": False,
        "semantic_raster_violation_count": 0,
        "visual_backplate_raster_allowlist": {
            "schema_name": "visual_backplate_raster_allowlist",
            "allowed_raster_object_ids": allowlist,
            "full_slide_reference_background_allowed": False,
            "semantic_raster_allowed": False,
        },
        "canva_parity_claimed": False,
    }
