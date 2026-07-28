"""Local procedural SVG icon synthesis for E01.3."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .procedural_svg_recipe_registry import RECIPE_BY_ROLE


SVG_BODY_BY_RECIPE = {
    "valve_pipeline_icon": '<path d="M3 15h18"/><path d="M12 6v9"/><circle cx="12" cy="6" r="3"/><path d="M8 6h8"/><circle cx="5" cy="15" r="1.5"/><circle cx="19" cy="15" r="1.5"/>',
    "chevron_next_icon": '<polyline points="9 5 16 12 9 19"/>',
    "hardhat_ppe_icon": '<path d="M4 14a8 8 0 0 1 16 0"/><path d="M3 14h18"/><path d="M7 14v3h10v-3"/><path d="M10 6v8"/><path d="M14 6v8"/><path d="M8 18h8"/>',
    "lock_zero_leak_icon": '<rect x="6" y="10" width="12" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><circle cx="12" cy="15" r="1"/><path d="M12 16v2"/>',
    "droplet_spill_control_icon": '<path d="M12 3C8 8 6 11 6 15a6 6 0 0 0 12 0c0-4-2-7-6-12z"/><path d="M9 15l2 2 4-5"/><path d="M4 21h16"/>',
    "chemical_barrier_icon": '<path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6l7-3z"/><path d="M8 15l8-8"/><path d="M8 8h8v8"/>',
    "users_teamwork_icon": '<circle cx="12" cy="7" r="3"/><circle cx="5" cy="10" r="2.3"/><circle cx="19" cy="10" r="2.3"/><path d="M6 21v-2a6 6 0 0 1 12 0v2"/><path d="M1.5 20v-1.5A4.5 4.5 0 0 1 8 15"/><path d="M22.5 20v-1.5A4.5 4.5 0 0 0 16 15"/>',
    "control_room_icon": '<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M7 17v3"/><path d="M17 17v3"/><path d="M8 10h3"/><path d="M13 10h3"/><path d="M8 13h8"/>',
    "pump_equipment_icon": '<rect x="6" y="8" width="9" height="8" rx="2"/><circle cx="10.5" cy="12" r="2"/><path d="M3 12h3"/><path d="M15 12h6"/><path d="M18 9v6"/><path d="M8 16v3h5v-3"/>',
    "gas_detection_icon": '<path d="M7 14a5 5 0 0 1 10 0v2a3 3 0 0 1-3 3h-4a3 3 0 0 1-3-3v-2z"/><circle cx="10" cy="14" r="1"/><circle cx="14" cy="14" r="1"/><path d="M9 18h6"/><path d="M18 6c1 1 1.5 2 1.5 3"/><path d="M20.5 4c1.6 1.6 2.4 3.2 2.4 5"/>',
    "footer_marker_icon": '<path d="M4 12h16"/><path d="M4 8h7"/><path d="M4 16h7"/><circle cx="19" cy="12" r="2"/>',
}


def generate_procedural_svgs(match_report: dict[str, Any], output_root: Path) -> dict[str, Any]:
    generated = []
    for match in match_report["matches"]:
        if match["classification"] != "GENERATED_PROCEDURAL_REQUIRED":
            continue
        role_id = match["role_id"]
        recipe_id = RECIPE_BY_ROLE[role_id]
        folder = output_root / _folder_for(match["target_component"])
        folder.mkdir(parents=True, exist_ok=True)
        svg_path = folder / f"{role_id}.svg"
        svg = _svg(SVG_BODY_BY_RECIPE[recipe_id])
        svg_path.write_text(svg, encoding="utf-8")
        generated.append(
            {
                "role_id": role_id,
                "recipe_id": recipe_id,
                "svg_path": svg_path.as_posix(),
                "sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest(),
                "source_type": "generated_procedural",
                "contains_bitmap": False,
                "contains_text_tag": False,
                "contains_external_reference": False,
            }
        )
    return {
        "schema_name": "generated_svg_icon_manifest",
        "status": "passed",
        "generated_count": len(generated),
        "generated_svgs": generated,
        "canva_parity_claimed": False,
    }


def _svg(body: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>\n"
    )


def _folder_for(component: str) -> str:
    return {
        "checklist": "checklist",
        "bottom_action_bar": "bottom_action_bar",
        "thumbnail_callouts": "thumbnail_callouts",
        "source_footer": "source_footer",
    }.get(component, "technical_overlay")

