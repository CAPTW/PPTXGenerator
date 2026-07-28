"""Z-order heuristics for fused E01X objects."""

from __future__ import annotations

from typing import Any


ROLE_Z_BASE = {
    "background_base": 0,
    "decorative_texture": 5,
    "shadow_or_glow": 8,
    "accent_line": 12,
    "hero_visual_field": 15,
    "replaceable_image_frame": 15,
    "card_panel": 25,
    "checklist_panel": 25,
    "connector": 32,
    "technical_overlay": 34,
    "icon_region": 42,
    "chart_region": 45,
    "table_region": 45,
    "matrix_region": 45,
    "process_node": 46,
    "timeline_phase": 46,
    "source_footer_strip": 48,
    "title_text_region": 55,
    "subtitle_text_region": 54,
    "body_text_region": 53,
    "unknown": 99,
}


def assign_z_order(role: str, index: int) -> int:
    return ROLE_Z_BASE.get(role, 90) + index


def build_z_order_graph(objects: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(objects, key=lambda item: item.get("z_order", 0))
    relationships = []
    for lower, upper in zip(ordered, ordered[1:]):
        relationships.append({"type": "below", "source": lower["object_id"], "target": upper["object_id"]})
        relationships.append({"type": "above", "source": upper["object_id"], "target": lower["object_id"]})
    return {
        "schema_name": "z_order_graph",
        "schema_version": "1.0",
        "object_count": len(objects),
        "objects": [{"object_id": obj["object_id"], "semantic_role": obj["semantic_role"], "z_order": obj["z_order"]} for obj in ordered],
        "relationships": relationships,
        "heuristics": [
            "background_base below everything",
            "decorative_texture above background but below semantic text",
            "hero_visual_field below overlay text/cards unless explicitly foreground",
            "card_panel below card text/icon",
            "icon above card panel",
            "text above card/panel",
            "footer strip above background and below footer text",
            "connector below text labels but above background/card if part of diagram",
        ],
        "canva_parity_claimed": False,
    }
