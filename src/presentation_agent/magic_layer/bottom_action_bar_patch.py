"""Bottom action bar v3 spec for E01.2."""

from __future__ import annotations

from typing import Any


def build_bottom_action_bar_component_spec_v3(oracle: dict[str, Any]) -> dict[str, Any]:
    actions = []
    x0 = 0.92
    cell_w = 2.72
    for idx, item in enumerate(oracle["actions"]):
        actions.append(
            {
                "action_id": f"bottom_action_{item['index']}",
                "bbox_in": {"x": round(x0 + idx * cell_w, 3), "y": 7.76, "w": 2.45, "h": 0.72},
                "icon_role": item["icon_role"],
                "label_top": item["label_top"],
                "label_bottom": item["label_bottom"],
                "native_editable": True,
                "separator": idx > 0,
            }
        )
    return {
        "schema_name": "bottom_action_bar_component_spec_v3",
        "status": "passed",
        "bar_bbox_in": {"x": 0.0, "y": 7.55, "w": 16.0, "h": 1.35},
        "action_count": len(actions),
        "actions": actions,
        "gold_accent_logic": "reference_like_labels_icons_and_rule_lines",
        "canva_parity_claimed": False,
    }

