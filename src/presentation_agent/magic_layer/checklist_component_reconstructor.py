"""Checklist component reconstruction spec for E01.1."""

from __future__ import annotations

from typing import Any


def build_checklist_component_spec(component_graph: dict[str, Any]) -> dict[str, Any]:
    component = _component(component_graph, "checklist_system")
    cards = []
    for step in component["step_cards"]:
        cards.append(
            {
                "card_id": f"step_card_{step['index']}",
                "number": step["number"],
                "heading": step["heading"],
                "body": step["body"],
                "icon_role": step["icon_role"],
                "objects": ["card_panel_shape", "number_text", "heading_text", "body_text", "vector_icon", "chevron_shape"],
                "all_semantic_objects_editable": True,
            }
        )
    return {
        "schema_name": "checklist_component_spec",
        "status": "passed" if len(cards) == 5 else "failed",
        "component_id": "checklist_system",
        "title": component["title"],
        "card_count": len(cards),
        "cards": cards,
        "raster_semantic_final_use_count": 0,
    }


def _component(component_graph: dict[str, Any], component_id: str) -> dict[str, Any]:
    return next(component for component in component_graph["components"] if component["component_id"] == component_id)

