from __future__ import annotations

from typing import Any


FORBIDDEN_RASTER_ROLES = {
    "full_slide_raster",
    "screenshot_slide",
    "semantic_text",
    "semantic_chart",
    "semantic_table",
    "semantic_timeline",
    "semantic_matrix",
    "semantic_roadmap",
    "footer_source",
}
ALLOWED_RASTER_ROLES = {"nonsemantic_photo", "hero_photo", "texture", "bounded_image_field"}


def default_raster_policy() -> dict[str, Any]:
    return {
        "allowed_raster_roles": sorted(ALLOWED_RASTER_ROLES),
        "forbidden_raster_roles": sorted(FORBIDDEN_RASTER_ROLES),
        "bounded_image_frame_requirements": ["bounded_bbox", "replaceable", "crop_editable", "no_baked_semantic_text"],
        "semantic_raster_blockers": ["semantic text", "chart/table/timeline/matrix/roadmap raster fallback"],
        "residual_raster_text_policy": "requires_B01_review_hook",
        "full_slide_raster_policy": "fatal",
        "screenshot_policy": "fatal",
        "validation_requirements": ["E01P semantic raster precompile", "B03 semantic editability"],
    }


def validate_raster_policy(policy: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if not policy.get("full_slide_raster_forbidden", policy.get("full_slide_raster_policy") == "fatal"):
        failures.append("full-slide raster must be forbidden")
    if not policy.get("semantic_raster_forbidden", True):
        failures.append("semantic raster fallback must be forbidden")
    return {"pass": not failures, "failures": failures}
