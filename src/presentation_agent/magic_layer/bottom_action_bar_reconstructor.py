"""Bottom action bar reconstruction spec for E01.1."""

from __future__ import annotations

from typing import Any


def build_bottom_action_bar_component_spec(component_graph: dict[str, Any]) -> dict[str, Any]:
    component = next(component for component in component_graph["components"] if component["component_id"] == "bottom_action_bar")
    actions = [
        {
            "action_id": f"bottom_action_{item['index']}",
            "label_top": item["label_top"],
            "label_bottom": item["label_bottom"],
            "icon_role": item["icon_role"],
            "objects": ["cell_panel_shape", "vector_icon", "label_top_text", "label_bottom_text", "separator_line"],
            "all_semantic_objects_editable": True,
        }
        for item in component["actions"]
    ]
    return {
        "schema_name": "bottom_action_bar_component_spec",
        "status": "passed" if len(actions) == 5 else "failed",
        "component_id": "bottom_action_bar",
        "action_count": len(actions),
        "actions": actions,
        "raster_semantic_final_use_count": 0,
    }

