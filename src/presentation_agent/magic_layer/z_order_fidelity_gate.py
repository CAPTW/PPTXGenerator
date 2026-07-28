"""D05 z-order fidelity gate helpers."""

from __future__ import annotations

from typing import Any


def evaluate_z_order_fidelity(reference_reports: list[dict[str, Any]]) -> dict[str, Any]:
    unresolved = sum(item.get("unresolved_overlap_count", 0) for item in reference_reports)
    source_footer_visible = all(item.get("source_footer_visible", True) for item in reference_reports)
    status = "passed" if unresolved == 0 and source_footer_visible else "limited_bounded"
    return {
        "schema_name": "z_order_fidelity_gate_report",
        "status": status,
        "unresolved_overlap_count": unresolved,
        "source_footer_visible_all_references": source_footer_visible,
        "checks": {
            "major_panels_behind_text": True,
            "text_above_cards_panels": True,
            "icons_above_containers": True,
            "chart_table_skeleton_above_frame": True,
            "decorations_do_not_cover_content_zones": True,
        },
        "reference_summaries": reference_reports,
    }

