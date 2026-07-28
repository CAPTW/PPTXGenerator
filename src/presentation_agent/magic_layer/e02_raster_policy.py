"""Raster policy gates for E02 candidates."""

from __future__ import annotations

from typing import Any


def build_raster_policy_report(archetype_id: str, media_ledger: dict[str, Any]) -> dict[str, Any]:
    full_slide = int(media_ledger.get("full_slide_raster_count", 0))
    screenshot = int(media_ledger.get("screenshot_slide_count", 0))
    semantic = int(media_ledger.get("semantic_raster_media_count", 0))
    status = "passed" if full_slide == 0 and screenshot == 0 and semantic == 0 else "failed"
    return {
        "schema_name": "raster_policy_report",
        "status": status,
        "archetype_id": archetype_id,
        "allowed_bounded_raster_media_count": int(media_ledger.get("allowed_bounded_raster_media_count", 0)),
        "raster_media_count": int(media_ledger.get("png_jpeg_media_count", 0)),
        "full_slide_raster_count": full_slide,
        "screenshot_slide_count": screenshot,
        "semantic_raster_violation_count": semantic,
        "reference_image_as_background": False,
    }


def build_unknown_layer_report(archetype_id: str, object_graph: dict[str, Any]) -> dict[str, Any]:
    count = int(object_graph.get("unknown_content_bearing_layer_count", 0))
    return {
        "schema_name": "unknown_layer_report",
        "status": "passed" if count == 0 else "failed",
        "archetype_id": archetype_id,
        "unknown_content_bearing_layer_count": count,
        "unknown_semantic_layer_count": 0,
        "decorative_unknown_bounded_count": 0,
    }


def summarize_raster_policy(archetype_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": "e02_raster_policy_summary",
        "status": "passed" if all(item["status"] == "passed" for item in archetype_reports.values()) else "failed",
        "raster_media_count": sum(int(item.get("raster_media_count", 0)) for item in archetype_reports.values()),
        "full_slide_raster_count": sum(int(item.get("full_slide_raster_count", 0)) for item in archetype_reports.values()),
        "screenshot_slide_count": sum(int(item.get("screenshot_slide_count", 0)) for item in archetype_reports.values()),
        "semantic_raster_violation_count": sum(int(item.get("semantic_raster_violation_count", 0)) for item in archetype_reports.values()),
        "archetypes": archetype_reports,
        "broad_canva_parity_claimed": False,
    }
