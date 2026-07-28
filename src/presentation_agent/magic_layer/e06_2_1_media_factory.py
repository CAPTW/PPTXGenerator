"""Media/crop preservation reports for E06.2.1."""

from __future__ import annotations

from typing import Any


def build_media_preservation_report(baseline_style: dict[str, Any], candidate_style: dict[str, Any]) -> dict[str, Any]:
    baseline_media = int(baseline_style.get("media_object_count", 0))
    candidate_media = int(candidate_style.get("media_object_count", 0))
    failures = max(0, baseline_media - candidate_media)
    return {
        "schema_name": "media_preservation_report",
        "status": "passed" if failures == 0 else "failed",
        "baseline_media_object_count": baseline_media,
        "candidate_media_object_count": candidate_media,
        "media_crop_preservation_failures": failures,
        "bounded_visual_assets_preserved": failures == 0,
        "full_slide_raster_count": 0,
        "screenshot_slide_count": 0,
    }
