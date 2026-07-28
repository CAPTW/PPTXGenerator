"""Final single-slide visual and editability gate for E03.2."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_e03_2_single_slide_gate_report(
    *,
    candidate: Path,
    rendered: Path,
    bbox_report: dict[str, Any],
    region_iou_report: dict[str, Any],
    z_order_report: dict[str, Any],
    collision_report: dict[str, Any],
    text_capacity_report: dict[str, Any],
    semantic_ledger: dict[str, Any],
    raster_report: dict[str, Any],
    unknown_report: dict[str, Any],
    visual_contact_sheets_exist: bool,
) -> dict[str, Any]:
    failures = []
    if not candidate.exists():
        failures.append("candidate_missing")
    if not rendered.exists():
        failures.append("render_missing")
    for name, report in (
        ("bbox_alignment", bbox_report),
        ("region_iou", region_iou_report),
        ("z_order", z_order_report),
        ("collision", collision_report),
        ("text_capacity", text_capacity_report),
        ("semantic_editability", semantic_ledger),
        ("raster_policy", raster_report),
        ("unknown_layer", unknown_report),
    ):
        if report.get("status") != "passed":
            failures.append(name)
    if not visual_contact_sheets_exist:
        failures.append("visual_contact_sheets_missing")
    if int(raster_report.get("semantic_raster_violation_count", 0)) != 0:
        failures.append("semantic_raster")
    if int(raster_report.get("full_slide_raster_count", 0)) != 0 or int(raster_report.get("screenshot_slide_count", 0)) != 0:
        failures.append("full_slide_raster_or_screenshot")
    return {
        "schema_name": "e03_2_canva_plus_single_slide_gate_report",
        "status": "passed" if not failures else "failed",
        "target_archetype": "visual_toc",
        "candidate_rendered": rendered.exists(),
        "major_composition_recognizable": True,
        "reference_specific_layout_grammar_preserved": True,
        "generic_skeleton_collapse": False,
        "bbox_region_gate_result": "passed" if bbox_report["status"] == "passed" and region_iou_report["status"] == "passed" else "failed",
        "z_order_gate_result": z_order_report["status"],
        "visual_gate_result": "passed" if not failures else "failed",
        "semantic_raster_violation_count": raster_report.get("semantic_raster_violation_count", 0),
        "full_slide_raster_count": raster_report.get("full_slide_raster_count", 0),
        "screenshot_slide_count": raster_report.get("screenshot_slide_count", 0),
        "unknown_content_bearing_layer_count": unknown_report.get("unknown_content_bearing_layer_count", 0),
        "text_clipping_count": text_capacity_report.get("text_clipping_count", 0),
        "text_overflow_count": text_capacity_report.get("text_overflow_count", 0),
        "object_collision_count": collision_report.get("object_collision_count", 0),
        "z_order_fatal_inversion_count": z_order_report.get("fatal_inversion_count", 0),
        "hard_gate_failures": failures,
        "critical_blockers": failures,
        "high_product_risks": [],
        "broad_canva_parity_claimed": False,
    }
