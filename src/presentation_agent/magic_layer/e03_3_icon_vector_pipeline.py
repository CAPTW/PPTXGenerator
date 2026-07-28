"""Curated v6 semantic icon validation for E03.3."""

from __future__ import annotations

from pathlib import Path
from typing import Any


EXPECTED_ICON_ROLES = {
    "cover_hero": ["calendar", "user", "flag"],
    "standard_content": ["database", "shield", "chart_bar", "note"],
    "data_dashboard": ["chart_bar", "database", "warning"],
    "table_heavy": ["database", "shield", "warning", "table"],
    "section_divider": ["flag"],
    "visual_toc": ["database", "network", "shield", "chart_bar", "document", "book", "calendar", "user"],
    "evidence_overview": ["evidence_trace", "database", "chart_bar", "shield", "warning"],
    "card_grid": ["chart_bar", "warning", "scale"],
    "methodology_framework": ["note", "process_node"],
    "process_flow": ["process_node", "flag", "decision_diamond"],
    "comparison_matrix": ["table", "scale", "decision_diamond"],
    "timeline_roadmap": ["clock", "risk_status"],
    "decision_record": ["decision_diamond", "evidence_trace", "document"],
    "risk_register": ["risk_status", "warning", "user"],
    "case_study": ["evidence_trace", "decision_diamond"],
    "closing_synthesis": ["recommendation", "evidence_trace"],
}


def build_icon_vector_ledger(archetype: str, curated_v6_root: Path, expected_roles: list[str] | None = None, forbidden_roles: set[str] | None = None) -> dict[str, Any]:
    forbidden_roles = forbidden_roles or set()
    expected_roles = expected_roles or EXPECTED_ICON_ROLES.get(archetype, [])
    rows = []
    unresolved = []
    for role in expected_roles:
        svg_path = curated_v6_root / f"{role}.svg"
        valid = svg_path.exists() and role not in forbidden_roles and _valid_svg(svg_path)
        rows.append({"role": role, "svg_path": svg_path.as_posix(), "status": "passed" if valid else "failed", "source_library": "magic_layer_v6"})
        if not valid:
            unresolved.append(role)
    return {"schema_name": "icon_vector_ledger", "status": "passed" if not unresolved else "failed", "archetype_id": archetype, "semantic_vector_icon_count": len(expected_roles) - len(unresolved), "semantic_raster_icon_count": 0, "unresolved_icon_count": len(unresolved), "unresolved_roles": unresolved, "rows": rows}


def _valid_svg(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    return "<svg" in text and "<image" not in text and "<text" not in text and "base64" not in text
