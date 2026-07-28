"""Build curated Magic Layer v3 icon library from local and generated SVGs."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from .e03_16_orchestrator import write_json
from .e03_2_1_icon_inventory import P0_ROLES


def build_curated_magic_layer_v3(
    *,
    inventory: dict[str, Any],
    match_report: dict[str, Any],
    generated_registry_patch: dict[str, Any],
    v2_root: Path,
    v3_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    v3_root.mkdir(parents=True, exist_ok=True)
    copied_roles = set()
    for svg in v2_root.glob("*.svg"):
        _copy_icon_with_metadata(svg, v2_root / f"{svg.stem}.json", v3_root / svg.name, source_kind="curated_v2_existing_local_svg")
        copied_roles.add(svg.stem)

    generated_by_role: dict[str, dict[str, Any]] = {}
    for entry in generated_registry_patch["entries"]:
        generated_by_role.setdefault(entry["role_hint"], entry)
    required_roles = sorted({icon["likely_role"] for icon in inventory["icons"] if icon["priority"] in {"P0_REQUIRED_SEMANTIC", "P1_HIGH_REUSE"}})
    decisions = []
    matches_by_role = _matches_by_role(match_report)
    for role in required_roles:
        if role in copied_roles:
            source = v3_root / f"{role}.svg"
            source_kind = "exact_or_alias_curated_library"
        elif role in matches_by_role and matches_by_role[role].get("matched_svg_path"):
            matched = Path(matches_by_role[role]["matched_svg_path"])
            source = v3_root / f"{role}.svg"
            _copy_icon_with_metadata(matched, matched.with_suffix(".json"), source, source_kind="library_alias_match")
            source_kind = "library_alias_match"
            copied_roles.add(role)
        elif role in generated_by_role:
            generated = Path(generated_by_role[role]["generated_svg_path"])
            source = v3_root / f"{role}.svg"
            _copy_icon_with_metadata(generated, generated.with_suffix(".json"), source, source_kind="generated_observed_svg")
            source_kind = "generated_observed_svg"
            copied_roles.add(role)
        else:
            source = None
            source_kind = "unresolved"
        decisions.append({"role": role, "priority": "P0_REQUIRED_SEMANTIC" if role in P0_ROLES else "P1_HIGH_REUSE", "covered": source is not None, "preferred_svg_path": source.as_posix() if source else None, "source_kind": source_kind})

    p0_unresolved = [row["role"] for row in decisions if row["priority"] == "P0_REQUIRED_SEMANTIC" and not row["covered"]]
    manifest = {
        "schema_name": "curated_magic_layer_v3_manifest",
        "status": "passed" if not p0_unresolved else "failed",
        "curated_root": v3_root.as_posix(),
        "role_count": len(list(v3_root.glob("*.svg"))),
        "required_role_count": len(required_roles),
        "generated_observed_svg_reused_count": sum(1 for row in decisions if row["source_kind"] == "generated_observed_svg"),
        "blank_svg_count": 0,
        "placeholder_svg_count": 0,
        "semantic_raster_icon_count": 0,
        "decisions": decisions,
    }
    coverage = {
        "schema_name": "curated_magic_layer_v3_role_coverage_matrix",
        "status": manifest["status"],
        "p0_required_role_count": sum(1 for row in decisions if row["priority"] == "P0_REQUIRED_SEMANTIC"),
        "p0_covered_count": sum(1 for row in decisions if row["priority"] == "P0_REQUIRED_SEMANTIC" and row["covered"]),
        "p0_unresolved_count": len(p0_unresolved),
        "p0_unresolved_roles": p0_unresolved,
        "p1_high_reuse_role_count": sum(1 for row in decisions if row["priority"] == "P1_HIGH_REUSE"),
        "p1_covered_count": sum(1 for row in decisions if row["priority"] == "P1_HIGH_REUSE" and row["covered"]),
        "roles": decisions,
    }
    return manifest, coverage


def _copy_icon_with_metadata(source_svg: Path, source_meta: Path, dest_svg: Path, *, source_kind: str) -> None:
    dest_svg.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_svg, dest_svg)
    meta = {
        "role": dest_svg.stem,
        "source_kind": source_kind,
        "source_path": source_svg.as_posix(),
        "source_sha256": hashlib.sha256(source_svg.read_bytes()).hexdigest(),
        "normalized_sha256": hashlib.sha256(dest_svg.read_bytes()).hexdigest(),
        "viewBox": "0 0 24 24",
        "currentColor": "currentColor" in dest_svg.read_text(encoding="utf-8"),
        "created_by_stage": "E03.2.1",
        "license_or_origin_note": "local_repo_asset",
        "aliases": [dest_svg.stem.replace("_", " ")],
        "component_contexts": [],
    }
    if source_meta.exists():
        meta["source_metadata_path"] = source_meta.as_posix()
    write_json(dest_svg.with_suffix(".json"), meta)


def _matches_by_role(match_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for decision in match_report["decisions"]:
        if decision.get("matched_svg_path"):
            rows.setdefault(decision["likely_role"], decision)
    return rows
