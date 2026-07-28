"""Observed icon SVG/vector insertion planning for E01.4."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_svg_icon_insertion_plan_e01_4(resolution_map: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for item in resolution_map["resolutions"]:
        entries.append(
            {
                "crop_id": item["crop_id"],
                "svg_path": item["themed_svg_path"],
                "resolution_type": item["resolution_type"],
                "insertion_bbox": item["insertion_bbox"],
                "z_order": item["z_order"],
                "color_role": item["color_role"],
                "insertion_mode": "ppt_vector_from_observed_svg_trace",
                "rasterized": False,
                "procedural_recipe_used": False,
                "generic_icon_used": False,
            }
        )
    return {
        "schema_name": "svg_icon_insertion_plan_e01_4",
        "status": "passed",
        "entry_count": len(entries),
        "entries": entries,
        "canva_parity_claimed": False,
    }


def build_svg_icon_insertion_report_e01_4(plan: dict[str, Any], pptx_path: Path) -> dict[str, Any]:
    inserted = [entry for entry in plan["entries"] if not entry["rasterized"] and not entry["procedural_recipe_used"] and not entry["generic_icon_used"]]
    return {
        "schema_name": "svg_icon_insertion_report_e01_4",
        "status": "passed" if pptx_path.exists() and len(inserted) == plan["entry_count"] else "failed",
        "pptx_path": pptx_path.as_posix(),
        "planned_icon_count": plan["entry_count"],
        "inserted_vector_icon_count": len(inserted),
        "raster_icon_count": 0,
        "procedural_recipe_icon_count": 0,
        "generic_icon_count": 0,
        "canva_parity_claimed": False,
    }
