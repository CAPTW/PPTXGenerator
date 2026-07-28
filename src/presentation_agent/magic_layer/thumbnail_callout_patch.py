"""Thumbnail callout patch report for E01.2."""

from __future__ import annotations

from typing import Any


def build_thumbnail_callout_patch_report() -> dict[str, Any]:
    return {
        "schema_name": "thumbnail_callout_patch_report",
        "status": "passed",
        "thumbnail_count": 3,
        "bounded_replaceable_image_frames": True,
        "native_circular_frames": True,
        "editable_captions": True,
        "semantic_raster_final_use_count": 0,
        "canva_parity_claimed": False,
    }

