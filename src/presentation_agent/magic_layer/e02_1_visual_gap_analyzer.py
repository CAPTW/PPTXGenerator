"""Visual/reference fidelity gap analysis for E02.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

from .e02_1_region_requirement_matrix import required_regions


DEFECTS: dict[str, list[str]] = {
    "cover_hero": [
        "HERO_VISUAL_FIELD_PLACEHOLDER",
        "DIAGONAL_DIVIDER_CHROME_MISSING",
        "TECHNICAL_VISUAL_RICHNESS_LOSS",
    ],
    "standard_content": [
        "CARD_CHROME_SIMPLIFIED",
        "ANGLED_CARD_GEOMETRY_MISSING",
        "LEFT_TECHNICAL_CIRCUIT_CHROME_LOSS",
        "RIGHT_INSIGHT_RAIL_WEAK",
    ],
    "data_dashboard": [
        "DASHBOARD_DENSITY_LOSS",
        "CHART_FRAME_SIMPLIFIED",
        "SECONDARY_PANEL_CHROME_LOSS",
        "ANNOTATION_STRIP_MISSING",
    ],
    "table_heavy": [
        "DENSE_TABLE_CHROME_LOSS",
        "SIDE_RAIL_ICON_GROUP_MISSING",
        "HEADER_ICON_SYSTEM_WEAK",
        "KPI_NOTE_STRIP_SIMPLIFIED",
    ],
}


def analyze_visual_gap(archetype_id: str, reference_image: Path, rendered_candidate: Path) -> dict[str, Any]:
    metrics = _image_delta(reference_image, rendered_candidate)
    defects = DEFECTS[archetype_id]
    return {
        "schema_name": "e02_1_visual_defect_register",
        "status": "patch_required",
        "archetype_id": archetype_id,
        "visual_reference_fidelity_status": "INSUFFICIENT",
        "generic_skeleton_regression": True,
        "missing_major_regions": defects,
        "required_regions": required_regions(archetype_id),
        "reference_vs_e02_render_metrics": metrics,
        "decision": f"E02_1_PATCH_{archetype_id.upper()}_REFERENCE_FIDELITY",
    }


def build_visual_gap_matrix(defect_registers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": "e02_visual_gap_matrix",
        "status": "patch_required",
        "e02_visual_reference_fidelity_status": "INSUFFICIENT",
        "e03_product_unlock": "REVOKED_PENDING_E02_1",
        "archetypes": defect_registers,
        "gap_count": sum(len(row["missing_major_regions"]) for row in defect_registers.values()),
    }


def _image_delta(reference_image: Path, rendered_candidate: Path) -> dict[str, Any]:
    if not reference_image.exists() or not rendered_candidate.exists():
        return {"status": "missing_image", "visual_similarity_proxy": 0.0}
    with Image.open(reference_image) as ref, Image.open(rendered_candidate) as ren:
        ref_rgb = ref.convert("RGB").resize((640, 360), Image.Resampling.LANCZOS)
        ren_rgb = ren.convert("RGB").resize((640, 360), Image.Resampling.LANCZOS)
        diff = ImageChops.difference(ref_rgb, ren_rgb)
        mean_delta = sum(ImageStat.Stat(diff).mean) / 3.0
        return {
            "status": "measured",
            "mean_abs_rgb_delta": round(mean_delta, 3),
            "visual_similarity_proxy": round(max(0.0, 1.0 - mean_delta / 255.0), 3),
        }
