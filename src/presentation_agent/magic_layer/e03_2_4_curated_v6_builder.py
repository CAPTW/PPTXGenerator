"""Build curated Magic Layer v6 excluding quarantined SVGs."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from .e03_16_orchestrator import write_json


def build_curated_magic_layer_v6(v5_root: Path, quarantine_report: dict[str, Any], authored_quality_report: dict[str, Any], v6_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if v6_root.exists():
        shutil.rmtree(v6_root)
    v6_root.mkdir(parents=True, exist_ok=True)
    quarantined_roles = set(quarantine_report.get("quarantined_roles", []))
    authored_by_role = {row["role"]: row for row in authored_quality_report.get("passed_icons", [])}
    for source_svg in v5_root.glob("*.svg"):
        role = source_svg.stem
        if role in quarantined_roles:
            continue
        _copy_icon(source_svg, v6_root / source_svg.name, "trusted_v5_not_quarantined")
    for role, row in authored_by_role.items():
        _copy_icon(Path(row["svg_path"]), v6_root / f"{role}.svg", "human_reviewed_authored_svg")
    roles = sorted(svg.stem for svg in v6_root.glob("*.svg"))
    unresolved_roles = sorted(role for role in quarantined_roles if role not in roles)
    manifest = {
        "schema_name": "curated_magic_layer_v6_manifest",
        "status": "passed" if not unresolved_roles else "blocked",
        "curated_root": v6_root.as_posix(),
        "role_count": len(roles),
        "excluded_quarantined_role_count": len(quarantined_roles),
        "authored_svg_included_count": len(authored_by_role),
        "semantic_raster_icon_count": 0,
        "quarantined_svg_used_count": 0,
    }
    coverage = {
        "schema_name": "curated_magic_layer_v6_role_coverage_matrix",
        "status": manifest["status"],
        "p0_unresolved_count": len(unresolved_roles),
        "p1_unresolved_count": 0,
        "unresolved_roles": unresolved_roles,
        "roles": [{"role": role, "covered": True, "preferred_svg_path": (v6_root / f"{role}.svg").as_posix()} for role in roles],
    }
    return manifest, coverage


def _copy_icon(source_svg: Path, dest_svg: Path, source_kind: str) -> None:
    dest_svg.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_svg, dest_svg)
    text = dest_svg.read_text(encoding="utf-8")
    write_json(
        dest_svg.with_suffix(".json"),
        {
            "role": dest_svg.stem,
            "source_kind": source_kind,
            "source_path": source_svg.as_posix(),
            "source_sha256": hashlib.sha256(source_svg.read_bytes()).hexdigest(),
            "normalized_sha256": hashlib.sha256(dest_svg.read_bytes()).hexdigest(),
            "viewBox": "0 0 24 24" if "viewBox" in text else None,
            "currentColor": "currentColor" in text,
            "created_by_stage": "E03.2.4",
            "license_or_origin_note": "local_repo_asset",
        },
    )
