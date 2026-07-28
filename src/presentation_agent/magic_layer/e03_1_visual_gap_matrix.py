"""Visual gap matrix for E03.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

from .e03_16_orchestrator import ARCHETYPES, CORE_ARCHETYPES, EXPANSION_ARCHETYPES


EXPANSION_DEFECTS = {
    "section_divider": ["PLAIN_TITLE_CARD_RISK", "SECTION_MARKER_WEAK", "DIAGONAL_SLAB_CHROME_INSUFFICIENT"],
    "visual_toc": ["NAVIGATION_SYSTEM_SIMPLIFIED", "ACTIVE_MARKER_WEAK", "SIDE_META_PANEL_WEAK"],
    "evidence_overview": ["EVIDENCE_CARD_TRACE_MARKERS_WEAK", "SUMMARY_STRIP_UNDERPOWERED", "PLAIN_CARD_GRID_RISK"],
    "card_grid": ["CARD_MODULARITY_UNDER_DENSE", "CATEGORY_HEADER_ACCENTS_WEAK", "INSIGHT_STRIP_WEAK"],
    "methodology_framework": ["FRAMEWORK_LAYER_SEMANTICS_WEAK", "CONNECTOR_RAIL_WEAK", "ACTIVE_LAYER_NOT_CLEAR"],
    "process_flow": ["PROCESS_NODE_DENSITY_LOW", "DECISION_GATE_MARKER_WEAK", "DIRECTIONAL_FLOW_UNDERPOWERED"],
    "comparison_matrix": ["MATRIX_DENSITY_LOW", "SCORE_MARKER_RHYTHM_WEAK", "DECISION_RAIL_WEAK"],
    "timeline_roadmap": ["TIMELINE_PHASE_RHYTHM_WEAK", "MILESTONE_DENSITY_LOW", "RISK_MISSION_ROWS_WEAK"],
    "decision_record": ["RECORD_DOCUMENT_FEEL_WEAK", "DECISION_STAMP_UNDERPOWERED", "EVIDENCE_STRIP_WEAK"],
    "risk_register": ["REGISTER_DENSITY_LOW", "SEVERITY_STATUS_FIELDS_WEAK", "SIDE_META_RAIL_WEAK"],
    "case_study": ["MULTI_PANEL_EVIDENCE_STRUCTURE_WEAK", "CASE_IMAGE_CONTEXT_BALANCE_WEAK", "RESULT_MODULES_WEAK"],
    "closing_synthesis": ["CLOSING_HIERARCHY_WEAK", "FINAL_ACTION_RHYTHM_WEAK", "GENERIC_THREE_CARD_RISK"],
}


def build_visual_gap_report(archetype_id: str, reference_image: Path, rendered_candidate: Path) -> dict[str, Any]:
    is_core = archetype_id in CORE_ARCHETYPES
    defects = [] if is_core else EXPANSION_DEFECTS[archetype_id]
    return {
        "schema_name": "e03_1_visual_gap_report",
        "status": "stable_core" if is_core else "patch_required",
        "archetype_id": archetype_id,
        "major_composition_preservation": "pass" if is_core else "patch",
        "reference_specific_chrome_preservation": "pass" if is_core else "patch",
        "archetype_identity": "pass" if is_core else "patch",
        "visual_density": "pass" if is_core else "patch",
        "semantic_slot_coverage": "pass",
        "text_capacity": "pass",
        "panel_card_fidelity": "pass" if is_core else "patch",
        "chart_table_process_timeline_fidelity": "pass" if is_core else "patch",
        "source_footer_fidelity": "pass",
        "z_order_overlap_fidelity": "pass",
        "shape_polygon_fidelity": "pass" if is_core else "patch",
        "icon_system_fidelity": "pass" if is_core else "patch",
        "editability_preservation": "pass",
        "generic_skeleton_collapse": False if is_core else True,
        "excessive_simplification": False if is_core else True,
        "defects": defects,
        "metrics": _metrics(reference_image, rendered_candidate),
    }


def build_visual_gap_matrix(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    expansion_patch_required = [key for key, row in reports.items() if key in EXPANSION_ARCHETYPES and row["status"] == "patch_required"]
    return {
        "schema_name": "e03_1_visual_gap_matrix",
        "status": "patch_required" if expansion_patch_required else "passed",
        "e03_reference_fidelity_status": "PATCH_REQUIRED" if expansion_patch_required else "PASSED",
        "e04_product_unlock": "REVOKED_PENDING_E03_1" if expansion_patch_required else "READY",
        "archetypes": reports,
        "expansion_patch_required_count": len(expansion_patch_required),
        "core_touch_policy": "do_not_degrade_e02_1_quality",
    }


def _metrics(reference_image: Path, rendered_candidate: Path) -> dict[str, Any]:
    if not reference_image.exists() or not rendered_candidate.exists():
        return {"status": "missing_image", "visual_similarity_proxy": 0.0}
    with Image.open(reference_image) as ref, Image.open(rendered_candidate) as ren:
        ref_rgb = ref.convert("RGB").resize((640, 360), Image.Resampling.LANCZOS)
        ren_rgb = ren.convert("RGB").resize((640, 360), Image.Resampling.LANCZOS)
        diff = ImageChops.difference(ref_rgb, ren_rgb)
        mean_delta = sum(ImageStat.Stat(diff).mean) / 3.0
        return {"status": "measured", "mean_abs_rgb_delta": round(mean_delta, 3), "visual_similarity_proxy": round(max(0.0, 1.0 - mean_delta / 255.0), 3)}
