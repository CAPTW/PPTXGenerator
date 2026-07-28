"""Deterministic procedural SVG fallback for missing curated roles."""

from __future__ import annotations

from typing import Any


def procedural_svg_for_role(role: str) -> str:
    """Return a simple currentColor 24x24 line icon for a missing semantic role."""
    motif = _motif(role)
    body = {
        "document": "<path d='M7 3h7l3 3v15H7z'/><path d='M14 3v4h4'/><path d='M9 11h6M9 15h6'/>",
        "database": "<ellipse cx='12' cy='5' rx='7' ry='3'/><path d='M5 5v10c0 1.7 3.1 3 7 3s7-1.3 7-3V5'/><path d='M5 10c0 1.7 3.1 3 7 3s7-1.3 7-3'/>",
        "shield": "<path d='M12 3l7 3v5c0 4.5-2.8 8.1-7 10-4.2-1.9-7-5.5-7-10V6z'/><path d='M9 12l2 2 4-5'/>",
        "workflow": "<circle cx='6' cy='6' r='2'/><circle cx='18' cy='6' r='2'/><circle cx='12' cy='18' r='2'/><path d='M8 6h8M7 8l4 8M17 8l-4 8'/>",
        "people": "<circle cx='9' cy='8' r='3'/><circle cx='17' cy='9' r='2'/><path d='M4 20c.7-4 3-6 6-6s5.3 2 6 6'/><path d='M14 15c2.5.2 4.2 1.8 5 5'/>",
        "technology": "<rect x='6' y='6' width='12' height='12' rx='2'/><path d='M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3'/><circle cx='12' cy='12' r='2'/>",
        "business": "<path d='M4 20h16'/><path d='M6 20V7l6-3 6 3v13'/><path d='M9 10h1M14 10h1M9 14h1M14 14h1'/>",
        "ui": "<path d='M9 6l6 6-6 6'/>",
    }[motif]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>\n"
    )


def build_procedural_svg_generation_report(generated: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": "procedural_svg_generation_report",
        "status": "passed" if len(generated) <= 30 else "patch_required",
        "procedural_svg_generation_count": len(generated),
        "threshold": 30,
        "generated_roles": [entry["role"] for entry in generated],
        "remote_api_used": False,
        "image_generation_used": False,
        "raster_assets_created": False,
        "canva_parity_claimed": False,
    }


def _motif(role: str) -> str:
    if any(token in role for token in ["file", "document", "report", "note", "book", "citation", "source", "checklist", "clipboard"]):
        return "document"
    if any(token in role for token in ["data", "chart", "table", "metric", "kpi", "filter", "search", "percent"]):
        return "database"
    if any(token in role for token in ["risk", "shield", "warning", "lock", "key", "policy", "compliance", "approval", "exception"]):
        return "shield"
    if any(token in role for token in ["workflow", "route", "process", "decision", "timeline", "loop", "branch", "flow"]):
        return "workflow"
    if any(token in role for token in ["user", "team", "people", "owner", "reviewer", "council", "handshake"]):
        return "people"
    if any(token in role for token in ["ai", "brain", "chip", "network", "server", "cloud", "model", "automation", "settings", "api", "code"]):
        return "technology"
    if any(token in role for token in ["building", "bank", "factory", "globe", "briefcase", "trophy", "store", "anchor"]):
        return "business"
    return "ui"
