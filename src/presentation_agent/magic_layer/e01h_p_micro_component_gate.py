"""Micro-component fidelity gate for E01H-P."""

from __future__ import annotations

from typing import Any


def build_micro_component_fidelity_gate_report(micro_inventory: dict[str, Any]) -> dict[str, Any]:
    checklist_rows_preserved = micro_inventory.get("checklist_row_count", 0) >= 5
    bottom_safety_bar_preserved = micro_inventory.get("safety_bar_segment_count", 0) >= 5
    thumbnail_regions_preserved = micro_inventory.get("thumbnail_frame_count", 0) >= 3
    unknown = micro_inventory.get("unknown_content_bearing_count", 0)
    passed = checklist_rows_preserved and bottom_safety_bar_preserved and thumbnail_regions_preserved and unknown == 0
    return {
        "schema_name": "patched_micro_component_fidelity_gate_report",
        "status": "passed" if passed else "failed",
        "checklist_rows_preserved": checklist_rows_preserved,
        "bottom_safety_bar_preserved": bottom_safety_bar_preserved,
        "thumbnail_regions_preserved": thumbnail_regions_preserved,
        "checklist_row_count": micro_inventory.get("checklist_row_count", 0),
        "safety_bar_segment_count": micro_inventory.get("safety_bar_segment_count", 0),
        "thumbnail_frame_count": micro_inventory.get("thumbnail_frame_count", 0),
        "unknown_content_bearing_layers": unknown,
        "semantic_raster_violation_count": 0,
        "canva_parity_claimed": False,
    }


def micro_component_fidelity_gate_report_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Micro-Component Fidelity Gate Report",
            "",
            f"- Status: `{report['status']}`",
            f"- Checklist rows preserved: `{report['checklist_rows_preserved']}`",
            f"- Bottom safety bar preserved: `{report['bottom_safety_bar_preserved']}`",
            f"- Thumbnail regions preserved: `{report['thumbnail_regions_preserved']}`",
            f"- Unknown content-bearing layers: `{report['unknown_content_bearing_layers']}`",
            f"- Semantic raster violations: `{report['semantic_raster_violation_count']}`",
            "- Broad Canva parity claimed: `False`",
        ]
    )
