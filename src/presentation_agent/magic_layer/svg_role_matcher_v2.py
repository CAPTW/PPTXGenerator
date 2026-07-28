"""Role-aware SVG library matcher for E01.3."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .e01_3_semantic_icon_gap import REQUIRED_ICON_ROLES


EXACT_LIBRARY = {
    "gauge_execute_monitor": "tabler__gauge.svg",
    "shield_verify_confirm": "tabler__shield-check.svg",
    "chat_communicate_confirm": "tabler__message-check.svg",
    "source_database": "tabler__database.svg",
}

ALIAS_LIBRARY = {
    "checklist_plan_prepare": "tabler__circle-check.svg",
    "document_complete_record": "tabler__list-numbers.svg",
    "warning_wear_ppe": "tabler__alert-triangle.svg",
}

NEAR_LIBRARY = {
    "shield_chemical_barrier": "tabler__shield-check.svg",
}


def build_svg_library_role_match_report(icon_root: Path) -> dict[str, Any]:
    matches = []
    for requirement in REQUIRED_ICON_ROLES:
        role_id = requirement["role_id"]
        if role_id in EXACT_LIBRARY and (icon_root / EXACT_LIBRARY[role_id]).exists():
            classification = "LIBRARY_EXACT_MATCH"
            svg_path = icon_root / EXACT_LIBRARY[role_id]
            confidence = 0.96
            rationale = "Exact local Tabler role match."
        elif role_id in ALIAS_LIBRARY and (icon_root / ALIAS_LIBRARY[role_id]).exists():
            classification = "LIBRARY_ALIAS_MATCH"
            svg_path = icon_root / ALIAS_LIBRARY[role_id]
            confidence = 0.82
            rationale = "Semantically close alias from local Tabler subset."
        elif role_id in NEAR_LIBRARY and (icon_root / NEAR_LIBRARY[role_id]).exists():
            classification = "LIBRARY_NEAR_MATCH_ACCEPTABLE"
            svg_path = icon_root / NEAR_LIBRARY[role_id]
            confidence = 0.72
            rationale = "Near match accepted only as base; procedural exact counterpart is also available if needed."
        else:
            classification = "GENERATED_PROCEDURAL_REQUIRED"
            svg_path = None
            confidence = 0.0
            rationale = "No adequate local library role match; local procedural SVG recipe required."
        matches.append(
            {
                "role_id": role_id,
                "target_component": requirement["component"],
                "classification": classification,
                "svg_path": svg_path.as_posix() if svg_path else None,
                "confidence": confidence,
                "rationale": rationale,
                "generic_icon": False,
            }
        )
    return {
        "schema_name": "svg_library_role_match_report",
        "status": "passed",
        "icon_root": icon_root.as_posix(),
        "match_count": len(matches),
        "matches": matches,
        "canva_parity_claimed": False,
    }

