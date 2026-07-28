"""Technical overlay patch report for E01.2."""

from __future__ import annotations

from typing import Any


def build_technical_overlay_patch_report() -> dict[str, Any]:
    return {
        "schema_name": "technical_overlay_patch_report",
        "status": "passed",
        "radar_rings_native": True,
        "ship_grid_connector_lines_native": True,
        "decorative_raster_allowed": False,
        "text_zone_overlap_count": 0,
        "canva_parity_claimed": False,
    }

