"""Build curated Magic Layer v6 from approved E03.2.4A sources."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from .e03_16_orchestrator import write_json


def build_curated_magic_layer_v6(
    *,
    v5_root: Path,
    v6_root: Path,
    quarantined_svg_paths: set[str],
    placeholder_svg_paths: set[str],
    approved_library_report: dict[str, Any],
    authored_quality_report: dict[str, Any],
    unresolved_p0_count: int,
    unresolved_required_p1_count: int,
    quarantined_roles: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if v6_root.exists():
        shutil.rmtree(v6_root)
    v6_root.mkdir(parents=True, exist_ok=True)
    forbidden = {Path(path).resolve().as_posix() for path in quarantined_svg_paths | placeholder_svg_paths if path}
    blocked_roles = quarantined_roles or set()
    copied_roles: dict[str, dict[str, Any]] = {}
    quarantined_reused = 0
    placeholder_count = 0

    for source in v5_root.glob("*.svg"):
        if source.stem in blocked_roles:
            continue
        if source.resolve().as_posix() in forbidden:
            continue
        role = source.stem
        _copy_icon(source, v6_root / f"{role}.svg", "trusted_v5_not_quarantined")
        copied_roles[role] = {"role": role, "preferred_svg_path": (v6_root / f"{role}.svg").as_posix(), "source_kind": "trusted_v5_not_quarantined"}

    for row in approved_library_report.get("approved_library_matches", []):
        source = Path(row.get("source_path") or "")
        role = row.get("role") or source.stem
        if not source.exists():
            continue
        if source.resolve().as_posix() in forbidden:
            quarantined_reused += 1
            continue
        _copy_icon(source, v6_root / f"{role}.svg", "human_approved_library_match")
        copied_roles[role] = {"role": role, "preferred_svg_path": (v6_root / f"{role}.svg").as_posix(), "source_kind": "human_approved_library_match"}

    for row in authored_quality_report.get("passed_icons", []):
        source = Path(row.get("svg_path") or "")
        role = row.get("role") or source.stem
        if not source.exists():
            continue
        _copy_icon(source, v6_root / f"{role}.svg", "human_reviewed_authored_svg")
        copied_roles[role] = {"role": role, "preferred_svg_path": (v6_root / f"{role}.svg").as_posix(), "source_kind": "human_reviewed_authored_svg"}

    status = "passed" if unresolved_p0_count == 0 and unresolved_required_p1_count == 0 and quarantined_reused == 0 and placeholder_count == 0 else "blocked"
    roles = [copied_roles[key] for key in sorted(copied_roles)]
    manifest = {
        "schema_name": "curated_magic_layer_v6_manifest",
        "status": status,
        "curated_root": v6_root.as_posix(),
        "role_count": len(roles),
        "approved_library_match_count": len(approved_library_report.get("approved_library_matches", [])),
        "authored_svg_included_count": len(authored_quality_report.get("passed_icons", [])),
        "quarantined_svg_reused_count": quarantined_reused,
        "generic_placeholder_count": placeholder_count,
        "semantic_raster_icon_count": 0,
    }
    coverage = {
        "schema_name": "curated_magic_layer_v6_role_coverage_matrix",
        "status": status,
        "role_count": len(roles),
        "p0_unresolved_count": unresolved_p0_count,
        "p1_unresolved_count": unresolved_required_p1_count,
        "roles": roles,
    }
    return manifest, coverage


def _copy_icon(source_svg: Path, dest_svg: Path, source_kind: str) -> None:
    dest_svg.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_svg, dest_svg)
    write_json(
        dest_svg.with_suffix(".json"),
        {
            "role": dest_svg.stem,
            "source_kind": source_kind,
            "source_path": source_svg.as_posix(),
            "source_sha256": hashlib.sha256(source_svg.read_bytes()).hexdigest(),
            "created_by_stage": "E03.2.4A",
        },
    )
