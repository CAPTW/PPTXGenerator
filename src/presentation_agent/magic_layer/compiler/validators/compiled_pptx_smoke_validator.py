from __future__ import annotations

from pathlib import Path
from typing import Any

from ...audit.full_slide_raster_check import check_full_slide_raster
from ...audit.pptx_ooxml_audit import audit_pptx_package


def validate_compiled_minimal_pptx(pptx_path: str | Path) -> dict[str, Any]:
    audit = audit_pptx_package(pptx_path)
    raster = check_full_slide_raster(audit)
    text_shape_count = sum(int(slide.get("text_shape_count") or 0) for slide in audit.get("per_slide", []))
    picture_count = sum(int(slide.get("picture_count") or 0) for slide in audit.get("per_slide", []))
    media_count = len(audit.get("package_parts", {}).get("media", []))
    failures: list[str] = []

    if not audit.get("exists"):
        failures.append("PPTX file is missing.")
    if audit.get("errors"):
        failures.extend(str(error) for error in audit["errors"])
    if audit.get("slide_count") != 1:
        failures.append("Controlled minimal PPTX must contain exactly one slide.")
    if raster.get("full_slide_raster_count", 0) > 0:
        failures.append("Full-slide raster candidate detected.")
    if raster.get("screenshot_like_count", 0) > 0:
        failures.append("Screenshot-like candidate detected.")
    if text_shape_count < 1:
        failures.append("At least one editable text shape is required.")

    semantic_raster_violation_count = 0 if picture_count == 0 and media_count == 0 else picture_count
    unknown_content_bearing_count = 0 if picture_count == 0 and media_count == 0 else picture_count
    if semantic_raster_violation_count:
        failures.append("Media-backed semantic content is not allowed in the minimal smoke test.")

    return {
        "schema": "compiled_pptx_smoke_validator.v1",
        "validation_scope": "CONTROLLED_MINIMAL_COMPILER_SMOKE_TEST",
        "pptx_path": str(pptx_path),
        "pass": not failures,
        "status": "PASS" if not failures else "FAIL",
        "slide_count": audit.get("slide_count"),
        "slide_width_in": audit.get("slide_width_in"),
        "slide_height_in": audit.get("slide_height_in"),
        "text_shape_count": text_shape_count,
        "picture_count": picture_count,
        "media_count": media_count,
        "full_slide_raster_count": raster.get("full_slide_raster_count", 0),
        "screenshot_like_count": raster.get("screenshot_like_count", 0),
        "semantic_raster_violation_count": semantic_raster_violation_count,
        "unknown_content_bearing_count": unknown_content_bearing_count,
        "failures": failures,
        "warnings": audit.get("warnings", []) + raster.get("warnings", []),
        "ooxml_audit": audit,
        "full_slide_raster": raster,
        "product_pass": False,
        "render_generated": False,
    }
