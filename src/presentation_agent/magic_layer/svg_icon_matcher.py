"""Deterministic SVG role matcher for D03."""

from __future__ import annotations

from typing import Any

from .svg_library_inventory import find_svg_for_names
from .svg_icon_role_taxonomy import taxonomy_by_role


def match_svg_for_role(role: str, taxonomy: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    role_spec = taxonomy_by_role(taxonomy).get(role) or taxonomy_by_role(taxonomy).get("generic_icon")
    if not role_spec:
        return _unmapped(role, "role_not_in_taxonomy")
    names = list(role_spec.get("preferred_svg_names") or []) + list(role_spec.get("fallback_svg_names") or [])
    entry = find_svg_for_names(inventory, names)
    if not entry:
        return _unmapped(role, "no_local_svg_for_preferred_or_fallback_names", role_spec)
    return {
        "role": role,
        "status": "mapped",
        "selected_svg_path": entry["path"],
        "selected_svg_id": entry["icon_id"],
        "match_method": "deterministic_role_to_local_svg_alias",
        "confidence": 0.78 if role == "generic_icon" else 0.86,
        "raster_fallback_allowed": False,
        "role_spec": role_spec,
    }


def _unmapped(role: str, reason: str, role_spec: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "role": role,
        "status": "unmapped",
        "selected_svg_path": None,
        "selected_svg_id": None,
        "match_method": None,
        "confidence": 0.0,
        "raster_fallback_allowed": False,
        "unresolved_reason": reason,
        "role_spec": role_spec,
    }

