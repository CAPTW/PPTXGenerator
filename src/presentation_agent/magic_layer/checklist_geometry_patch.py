"""Checklist geometry v3 spec for E01.2."""

from __future__ import annotations

from typing import Any


def build_checklist_component_spec_v3(oracle: dict[str, Any]) -> dict[str, Any]:
    panel = {"x": 9.66, "y": 0.31, "w": 6.08, "h": 7.08}
    row_h = 1.12
    row_gap = 0.115
    rows = []
    for idx, step in enumerate(oracle["steps"]):
        y = panel["y"] + 0.82 + idx * (row_h + row_gap)
        rows.append(
            {
                "card_id": f"step_card_{step['index']}",
                "bbox_in": {"x": panel["x"] + 0.18, "y": round(y, 3), "w": panel["w"] - 0.36, "h": row_h},
                "icon_role": step["icon_role"],
                "number": step["number"],
                "heading": step["heading"],
                "body": step["body"],
                "chevron": True,
                "separator_lines": True,
                "native_editable": True,
            }
        )
    return {
        "schema_name": "checklist_component_spec_v3",
        "status": "passed",
        "panel_bbox_in": panel,
        "title_bbox_in": {"x": panel["x"] + 0.86, "y": panel["y"] + 0.25, "w": 4.35, "h": 0.36},
        "card_count": len(rows),
        "cards": rows,
        "geometry_patch": "tightened_to_reference_right_panel",
        "canva_parity_claimed": False,
    }

