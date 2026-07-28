"""Resolve semantic icon roles to curated v7.1 themed SVG variants."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def resolve_icon_v7_1_roles(
    archetype: str,
    roles: list[str],
    curated_v7_1_manifest: dict[str, Any],
    *,
    background: str = "light",
) -> dict[str, Any]:
    variants = curated_v7_1_manifest.get("variants_by_role", {})
    role_meta = {row["role_id"]: row for row in curated_v7_1_manifest.get("roles", [])}
    rows: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for role in roles:
        variant = variants.get(role, {})
        themed = variant.get(background) or variant.get("light")
        source = role_meta.get(role, {}).get("svg_path")
        valid = bool(themed and Path(themed).exists())
        if not valid:
            unresolved.append(role)
        rows.append(
            {
                "archetype_id": archetype,
                "semantic_role": role,
                "source_svg_path": source,
                "themed_svg_path": themed,
                "expected_background": background,
                "expected_color_variant": background,
                "priority": role_meta.get(role, {}).get("priority", "P0_REQUIRED_SEMANTIC"),
                "status": "resolved" if valid else "unresolved",
                "raster_fallback": False,
                "insertion_route": "true_svg_media_insertion",
                "source_library": "magic_layer_v7_1",
            }
        )
    return {
        "schema_name": "icon_v7_1_resolver_report",
        "status": "passed" if not unresolved else "failed",
        "archetype_id": archetype,
        "resolved_count": len(rows) - len(unresolved),
        "unresolved_count": len(unresolved),
        "unresolved_roles": unresolved,
        "rows": rows,
    }
