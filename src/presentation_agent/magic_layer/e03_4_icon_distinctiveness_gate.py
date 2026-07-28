"""Distinctiveness and small-size legibility gates for curated icon libraries."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .e03_4_authored_svg_quality_gate import primitive_count, validate_svg_text
from .e03_4_icon_role_taxonomy import ROLE_FAMILIES


def build_icon_distinctiveness_report(curated_manifest: dict[str, Any]) -> dict[str, Any]:
    p0_roles = [row for row in curated_manifest.get("roles", []) if row.get("priority") == "P0_REQUIRED_SEMANTIC"]
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for row in p0_roles:
        svg_path = Path(row.get("svg_path") or "")
        if not svg_path.exists():
            continue
        digest = hashlib.sha256(_normalized_svg(svg_path.read_text(encoding="utf-8")).encode("utf-8")).hexdigest()
        by_hash.setdefault(digest, []).append(row)
    duplicate_groups: list[dict[str, Any]] = []
    for digest, rows in by_hash.items():
        families = {row.get("family") or ROLE_FAMILIES.get(row.get("role_id", ""), "general") for row in rows}
        if len(rows) > 1 and len(families) > 1:
            duplicate_groups.append({"hash": digest, "roles": [row["role_id"] for row in rows], "families": sorted(families)})
    return {
        "schema_name": "icon_distinctiveness_report",
        "status": "passed" if not duplicate_groups else "failed",
        "checked_p0_icon_count": len(p0_roles),
        "duplicate_unrelated_p0_count": len(duplicate_groups),
        "duplicate_unrelated_p0_groups": duplicate_groups,
    }


def build_small_size_legibility_report(curated_manifest: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    rows = curated_manifest.get("roles", [])
    for row in rows:
        svg_path = Path(row.get("svg_path") or "")
        text = svg_path.read_text(encoding="utf-8") if svg_path.exists() else ""
        quality_failures = validate_svg_text(text, role_id=row.get("role_id", svg_path.stem))
        primitives = primitive_count(text)
        if quality_failures or primitives == 0:
            failures.append({**row, "quality_failures": quality_failures, "primitive_count": primitives})
    return {
        "schema_name": "icon_small_size_legibility_report",
        "status": "passed" if not failures else "failed",
        "checked_icon_count": len(rows),
        "failed_count": len(failures),
        "failures": failures,
    }


def _normalized_svg(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())
