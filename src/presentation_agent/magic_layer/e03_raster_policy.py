"""Raster and unknown layer policy for E03."""

from __future__ import annotations

from typing import Any


def build_raster_policy_report(archetype_id: str, media_ledger: dict[str, Any], visual_asset_plan: dict[str, Any]) -> dict[str, Any]:
    full_slide = int(media_ledger.get("full_slide_raster_count", 0))
    screenshot = int(media_ledger.get("screenshot_slide_count", 0))
    semantic = int(media_ledger.get("semantic_raster_media_count", 0))
    return {
        "schema_name": "raster_policy_report",
        "status": "passed" if full_slide == 0 and screenshot == 0 and semantic == 0 else "failed",
        "archetype_id": archetype_id,
        "raster_media_count": int(media_ledger.get("png_jpeg_media_count", 0)),
        "bounded_visual_asset_count": int(visual_asset_plan.get("bounded_visual_asset_count", 0)),
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


def summarize_raster_policy(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": "e03_raster_policy_summary",
        "status": "passed" if all(row["status"] == "passed" for row in reports.values()) else "failed",
        "raster_media_count": sum(int(row["raster_media_count"]) for row in reports.values()),
        "bounded_visual_asset_count": sum(int(row["bounded_visual_asset_count"]) for row in reports.values()),
        "full_slide_raster_count": sum(int(row["full_slide_raster_count"]) for row in reports.values()),
        "screenshot_slide_count": sum(int(row["screenshot_slide_count"]) for row in reports.values()),
        "semantic_raster_violation_count": sum(int(row["semantic_raster_violation_count"]) for row in reports.values()),
        "broad_canva_parity_claimed": False,
        "archetypes": reports,
    }
