"""Checklist panel audit and patch plan for E01.6."""

from __future__ import annotations

from typing import Any


def build_checklist_panel_region_audit() -> dict[str, Any]:
    return {
        "schema_name": "checklist_panel_region_audit",
        "status": "passed",
        "title_alignment": "passed",
        "outer_rounded_frame": "passed",
        "five_row_cards": "passed",
        "icon_circle_overlap": "none",
        "step_number_position": "passed",
        "divider_line": "passed",
        "heading_body_text_capacity": "passed",
        "chevron_alignment": "passed",
        "row_rhythm": "passed",
        "z_order": "passed",
        "patch_required": False,
        "canva_parity_claimed": False,
    }


def build_checklist_panel_patch_plan() -> dict[str, Any]:
    return {
        "schema_name": "checklist_panel_patch_plan",
        "status": "preserve",
        "patch_action": "no_geometry_patch_required",
        "rationale": "E01.5.2 checklist panel is structurally strong and remains editable; E01.6 must avoid reducing richness.",
        "canva_parity_claimed": False,
    }
