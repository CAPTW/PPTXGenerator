"""Procedural SVG recipe registry for missing E01.3 semantic icon roles."""

from __future__ import annotations

from typing import Any


RECIPE_BY_ROLE = {
    "valve_setup_secure": "valve_pipeline_icon",
    "chevron_next": "chevron_next_icon",
    "hardhat_or_ppe": "hardhat_ppe_icon",
    "lock_zero_leak": "lock_zero_leak_icon",
    "droplet_or_spill_control": "droplet_spill_control_icon",
    "shield_chemical_barrier": "chemical_barrier_icon",
    "users_teamwork": "users_teamwork_icon",
    "cargo_control_room": "control_room_icon",
    "pump_or_equipment": "pump_equipment_icon",
    "gas_detection_or_respirator": "gas_detection_icon",
    "footer_marker": "footer_marker_icon",
}


def build_procedural_svg_recipe_registry() -> dict[str, Any]:
    recipes = []
    for role_id, recipe_id in RECIPE_BY_ROLE.items():
        recipes.append(
            {
                "role_id": role_id,
                "recipe_id": recipe_id,
                "viewBox": "0 0 24 24",
                "allowed_primitives": ["path", "line", "polyline", "circle", "rect", "ellipse", "polygon"],
                "forbidden": ["image", "text", "script", "style", "external_href", "base64_bitmap"],
                "stroke_linecap": "round",
                "stroke_linejoin": "round",
            }
        )
    return {
        "schema_name": "procedural_svg_recipe_registry",
        "status": "passed",
        "recipe_count": len(recipes),
        "recipes": recipes,
        "canva_parity_claimed": False,
    }

