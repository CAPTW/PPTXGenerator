from __future__ import annotations

from typing import Any


def check_full_slide_raster(ooxml_audit: dict[str, Any], *, product_candidate: bool = True) -> dict[str, Any]:
    slide_width = ooxml_audit.get("slide_width_emu")
    slide_height = ooxml_audit.get("slide_height_emu")
    findings: list[dict[str, Any]] = []
    violations: list[str] = []
    warnings: list[str] = []
    max_media_ratio = 0.0
    full_count = 0
    screenshot_count = 0

    for slide in ooxml_audit.get("per_slide", []):
        slide_findings: list[dict[str, Any]] = []
        text_count = int(slide.get("text_shape_count") or 0)
        picture_count = int(slide.get("picture_count") or 0)
        for picture in slide.get("pictures", []):
            area_ratio = picture.get("area_ratio")
            width_ratio = picture.get("width_ratio")
            height_ratio = picture.get("height_ratio")
            if isinstance(area_ratio, (int, float)):
                max_media_ratio = max(max_media_ratio, float(area_ratio))
            if area_ratio is None:
                warnings.append(f"Slide {slide.get('slide_id')} picture geometry is unknown.")
                continue
            name = str(picture.get("name", ""))
            full_slide = area_ratio >= 0.95 or (
                isinstance(width_ratio, (int, float))
                and isinstance(height_ratio, (int, float))
                and width_ratio >= 0.95
                and height_ratio >= 0.95
            )
            screenshot_like = (
                area_ratio >= 0.80
                and text_count <= 1
                and (picture_count == 1 or _name_suggests_screenshot(name))
            )
            if full_slide:
                full_count += 1
                slide_findings.append({"type": "FULL_SLIDE_RASTER", "picture": picture})
            if screenshot_like:
                screenshot_count += 1
                slide_findings.append({"type": "SCREENSHOT_LIKE_RASTER", "picture": picture})
        if picture_count and slide.get("geometry_status") == "UNKNOWN":
            warnings.append(f"Slide {slide.get('slide_id')} has pictures but insufficient geometry for strict raster sizing.")
        findings.append(
            {
                "slide_id": slide.get("slide_id"),
                "picture_count": picture_count,
                "text_shape_count": text_count,
                "findings": slide_findings,
            }
        )

    if product_candidate and full_count:
        violations.append("Full-slide raster candidate detected.")
    if product_candidate and screenshot_count:
        violations.append("Screenshot-like slide candidate detected.")

    return {
        "schema_name": "full_slide_raster_check.v1",
        "full_slide_raster_count": full_count,
        "screenshot_like_count": screenshot_count,
        "media_dominance_ratio": round(max_media_ratio, 6),
        "per_slide_findings": findings,
        "violations": violations,
        "warnings": warnings,
        "confidence": "HIGH" if not warnings else "MEDIUM",
        "pass": not violations,
        "slide_width_emu": slide_width,
        "slide_height_emu": slide_height,
    }


def _name_suggests_screenshot(name: str) -> bool:
    lower = name.lower()
    return any(token in lower for token in ("screenshot", "render", "contact sheet", "reference"))
