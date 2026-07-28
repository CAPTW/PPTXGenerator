"""Build curated Magic Layer icon library v7 from audited v6 plus authored gaps."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def build_curated_magic_layer_v7(
    *,
    taxonomy: dict[str, Any],
    audit: dict[str, Any],
    authored_quality: dict[str, Any],
    v6_root: Path,
    v7_root: Path,
    quarantined_svg_paths: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if v7_root.exists():
        shutil.rmtree(v7_root)
    v7_root.mkdir(parents=True, exist_ok=True)
    forbidden = {Path(path).resolve().as_posix() for path in quarantined_svg_paths if path}
    audit_by_role = audit.get("role_audits_by_role", {})
    authored_by_role = {row["role_id"]: row for row in authored_quality.get("passed_icons", [])}
    roles: list[dict[str, Any]] = []
    unresolved_p0 = 0
    unresolved_p1 = 0
    generic_placeholder_p0 = 0
    quarantined_reused = 0

    for role in taxonomy.get("roles", []):
        role_id = role["role_id"]
        audit_row = audit_by_role.get(role_id, {})
        source_path: Path | None = None
        source_kind = ""
        if audit_row.get("status") == "accepted":
            candidate = Path(audit_row.get("svg_path") or v6_root / f"{role_id}.svg")
            if candidate.exists() and candidate.resolve().as_posix() not in forbidden:
                source_path = candidate
                source_kind = "accepted_v6"
        if source_path is None and role_id in authored_by_role:
            candidate = Path(authored_by_role[role_id]["svg_path"])
            if candidate.exists():
                source_path = candidate
                source_kind = "authored_v7"
        if source_path is None:
            if role["priority"] == "P0_REQUIRED_SEMANTIC":
                unresolved_p0 += 1
            else:
                unresolved_p1 += 1
            continue
        if source_path.resolve().as_posix() in forbidden:
            quarantined_reused += 1
            continue
        dest = v7_root / f"{role_id}.svg"
        shutil.copy2(source_path, dest)
        svg_bytes = dest.read_bytes()
        render_hash = hashlib.sha256(svg_bytes).hexdigest()
        metadata = {
            "role_id": role_id,
            "priority": role["priority"],
            "family": role["family"],
            "aliases": role["aliases"],
            "provenance": source_kind,
            "source_path": source_path.as_posix(),
            "render_hash": render_hash,
            "created_by_stage": "E03.4",
        }
        dest.with_suffix(".json").write_text(json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        roles.append(
            {
                "role_id": role_id,
                "priority": role["priority"],
                "family": role["family"],
                "svg_path": dest.as_posix(),
                "metadata_path": dest.with_suffix(".json").as_posix(),
                "source_kind": source_kind,
                "render_hash": render_hash,
            }
        )
        if audit_row.get("placeholder_like") and role["priority"] == "P0_REQUIRED_SEMANTIC" and source_kind == "accepted_v6":
            generic_placeholder_p0 += 1

    p0_role_count = sum(row["priority"] == "P0_REQUIRED_SEMANTIC" for row in roles)
    p1_role_count = sum(row["priority"] == "P1_HIGH_REUSE" for row in roles)
    status = "passed" if unresolved_p0 == 0 and quarantined_reused == 0 and generic_placeholder_p0 == 0 else "blocked"
    manifest = {
        "schema_name": "curated_magic_layer_v7_manifest",
        "status": status,
        "curated_root": v7_root.as_posix(),
        "role_count": len(roles),
        "p0_role_count": p0_role_count,
        "p1_role_count": p1_role_count,
        "accepted_v6_icon_count": sum(row["source_kind"] == "accepted_v6" for row in roles),
        "authored_svg_v7_count": sum(row["source_kind"] == "authored_v7" for row in roles),
        "unresolved_p0_count": unresolved_p0,
        "unresolved_p1_count": unresolved_p1,
        "generic_placeholder_p0_count": generic_placeholder_p0,
        "quarantined_svg_reused_count": quarantined_reused,
        "semantic_raster_icon_count": 0,
        "roles": roles,
    }
    coverage = {
        "schema_name": "curated_magic_layer_v7_role_coverage_matrix",
        "status": status,
        "role_count": len(roles),
        "p0_role_count": p0_role_count,
        "p1_role_count": p1_role_count,
        "unresolved_p0_count": unresolved_p0,
        "unresolved_p1_count": unresolved_p1,
        "generic_placeholder_p0_count": generic_placeholder_p0,
        "semantic_raster_icon_count": 0,
        "roles": roles,
    }
    return manifest, coverage
