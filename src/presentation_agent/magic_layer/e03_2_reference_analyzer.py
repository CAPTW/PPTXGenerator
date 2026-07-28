"""Reference-region analysis for the E03.2 visual_toc golden slide."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image


VISUAL_TOC_BBOXES = {
    "background_base": (0.000, 0.000, 1.000, 1.000),
    "dark_header_region": (0.000, 0.000, 1.000, 0.255),
    "title_region": (0.085, 0.040, 0.330, 0.185),
    "header_meta_region": (0.330, 0.095, 0.430, 0.185),
    "technical_overlay_region": (0.700, 0.020, 0.995, 0.205),
    "main_stage_region": (0.000, 0.250, 1.000, 0.875),
    "progress_path_region": (0.070, 0.285, 0.755, 0.382),
    "module_card_group": (0.020, 0.382, 0.780, 0.765),
    "module_card_01": (0.024, 0.382, 0.140, 0.760),
    "module_card_02_active": (0.151, 0.382, 0.282, 0.760),
    "module_card_03": (0.298, 0.382, 0.420, 0.760),
    "module_card_04": (0.431, 0.382, 0.552, 0.760),
    "module_card_05": (0.564, 0.382, 0.670, 0.760),
    "module_card_06": (0.680, 0.382, 0.780, 0.760),
    "right_meta_panel": (0.797, 0.242, 0.982, 0.815),
    "reading_path_region": (0.055, 0.770, 0.765, 0.825),
    "source_footer_strip": (0.000, 0.875, 1.000, 1.000),
    "footer_source_cluster": (0.020, 0.890, 0.195, 0.985),
    "footer_meta_cluster": (0.225, 0.890, 0.585, 0.985),
    "footer_label_cluster": (0.710, 0.895, 0.850, 0.975),
    "footer_gold_wedge": (0.870, 0.875, 1.000, 1.000),
}

CARD_IDS = ("module_card_01", "module_card_02_active", "module_card_03", "module_card_04", "module_card_05", "module_card_06")


def analyze_e03_2_reference(archetype_id: str, reference_image: Path) -> dict[str, Any]:
    if archetype_id != "visual_toc":
        raise ValueError(f"E03.2 golden analyzer only supports visual_toc, got {archetype_id}")
    with Image.open(reference_image) as image:
        width, height = image.size
    regions = []
    for idx, (region_id, bbox_norm) in enumerate(VISUAL_TOC_BBOXES.items()):
        regions.append(
            {
                "region_id": region_id,
                "semantic_role": _role(region_id),
                "bbox_norm": list(bbox_norm),
                "bbox_px": _to_px(bbox_norm, width, height),
                "content_bearing": region_id not in {"background_base", "technical_overlay_region"},
                "editable_target": _editable_target(region_id),
                "visual_priority": _priority(region_id),
                "must_preserve": region_id not in {"background_base"},
                "expected_z_order": idx * 10,
                "protected_text_zone": "title" in region_id or "footer" in region_id or region_id in CARD_IDS or region_id == "right_meta_panel",
            }
        )
    return {
        "schema_name": "e03_2_reference_analysis_report",
        "status": "passed",
        "target_archetype": archetype_id,
        "reference_image": reference_image.as_posix(),
        "canvas_px": {"width": width, "height": height},
        "major_regions": regions,
        "expected_reading_order": [
            "title_region",
            "progress_path_region",
            *CARD_IDS,
            "right_meta_panel",
            "reading_path_region",
            "source_footer_strip",
        ],
        "expected_z_order": [
            "background_base",
            "dark_header_region",
            "main_stage_region",
            "technical_overlay_region",
            "progress_path_region",
            "module_card_group",
            *CARD_IDS,
            "right_meta_panel",
            "reading_path_region",
            "source_footer_strip",
        ],
        "optional_decorative_zones": ["technical_overlay_region"],
        "semantic_raster_allowed": False,
        "full_slide_raster_allowed": False,
    }


def _to_px(bbox: tuple[float, float, float, float], width: int, height: int) -> list[int]:
    x0, y0, x1, y1 = bbox
    return [round(x0 * width), round(y0 * height), round((x1 - x0) * width), round((y1 - y0) * height)]


def _role(region_id: str) -> str:
    if region_id.startswith("module_card"):
        return "navigation_module_card"
    if "footer" in region_id or "source" in region_id:
        return "source_footer_strip"
    if "meta" in region_id:
        return "metadata_panel"
    if "path" in region_id:
        return "navigation_connector"
    if "title" in region_id:
        return "title_text_region"
    if "technical" in region_id:
        return "technical_overlay"
    if "stage" in region_id:
        return "content_stage"
    return region_id


def _editable_target(region_id: str) -> str:
    if region_id in {"background_base", "technical_overlay_region"}:
        return "ppt_native_decorative_shape"
    if region_id.startswith("module_card") or "panel" in region_id or "stage" in region_id or "footer" in region_id:
        return "ppt_shapes_text_icons"
    if "path" in region_id:
        return "ppt_connectors_lines"
    return "ppt_editable_text_shape"


def _priority(region_id: str) -> str:
    if region_id in {"title_region", "module_card_group", "right_meta_panel", "progress_path_region"}:
        return "high"
    if "footer" in region_id or "path" in region_id:
        return "medium"
    return "low"
