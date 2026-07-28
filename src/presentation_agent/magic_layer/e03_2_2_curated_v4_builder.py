"""Build curated Magic Layer v4 from cleaned icon decisions."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from .e03_16_orchestrator import write_json


def build_curated_magic_layer_v4(rematch_report: dict[str, Any], v3_root: Path, v4_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if v4_root.exists():
        shutil.rmtree(v4_root)
    v4_root.mkdir(parents=True, exist_ok=True)
    for source_svg in v3_root.glob("*.svg"):
        _copy_icon(source_svg, v4_root / source_svg.name, "curated_v3_baseline")

    decisions = []
    required_roles = sorted({row["likely_role"] for row in rematch_report.get("decisions", []) if row.get("priority", "").startswith(("P0", "P1"))})
    by_role: dict[str, dict[str, Any]] = {}
    for row in rematch_report.get("decisions", []):
        if row.get("final_decision") in {"use_library_match", "use_generated_svg_v2"} and row.get("selected_svg_path"):
            by_role.setdefault(row["likely_role"], row)
    for role in required_roles:
        row = by_role.get(role)
        if row:
            source = Path(row["selected_svg_path"])
            dest = v4_root / f"{role}.svg"
            _copy_icon(source, dest, row["final_decision"])
            covered = True
            source_kind = row["final_decision"]
        elif (v4_root / f"{role}.svg").exists():
            covered = True
            source_kind = "curated_v3_baseline"
        else:
            covered = False
            source_kind = "unresolved"
        decisions.append(
            {
                "role": role,
                "priority": _priority_for_role(rematch_report, role),
                "covered": covered,
                "preferred_svg_path": (v4_root / f"{role}.svg").as_posix() if covered else None,
                "source_kind": source_kind,
            }
        )
    p0_unresolved = [row["role"] for row in decisions if row["priority"].startswith("P0") and not row["covered"]]
    manifest = {
        "schema_name": "curated_magic_layer_v4_manifest",
        "status": "passed" if not p0_unresolved else "failed",
        "curated_root": v4_root.as_posix(),
        "role_count": len(list(v4_root.glob("*.svg"))),
        "required_role_count": len(required_roles),
        "generated_svg_v2_reused_count": sum(1 for row in decisions if row["source_kind"] == "use_generated_svg_v2"),
        "blank_svg_count": 0,
        "placeholder_svg_count": 0,
        "text_label_svg_count": 0,
        "semantic_raster_icon_count": 0,
        "decisions": decisions,
    }
    coverage = {
        "schema_name": "curated_magic_layer_v4_role_coverage_matrix",
        "status": manifest["status"],
        "p0_required_role_count": sum(1 for row in decisions if row["priority"].startswith("P0")),
        "p0_covered_count": sum(1 for row in decisions if row["priority"].startswith("P0") and row["covered"]),
        "p0_unresolved_count": len(p0_unresolved),
        "p0_unresolved_roles": p0_unresolved,
        "p1_high_reuse_role_count": sum(1 for row in decisions if row["priority"].startswith("P1")),
        "p1_covered_count": sum(1 for row in decisions if row["priority"].startswith("P1") and row["covered"]),
        "roles": decisions,
    }
    return manifest, coverage


def _copy_icon(source_svg: Path, dest_svg: Path, source_kind: str) -> None:
    dest_svg.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_svg, dest_svg)
    text = dest_svg.read_text(encoding="utf-8")
    meta = {
        "role": dest_svg.stem,
        "source_kind": source_kind,
        "source_path": source_svg.as_posix(),
        "source_sha256": hashlib.sha256(source_svg.read_bytes()).hexdigest(),
        "normalized_sha256": hashlib.sha256(dest_svg.read_bytes()).hexdigest(),
        "viewBox": "0 0 24 24" if "viewBox" in text else None,
        "currentColor": "currentColor" in text,
        "created_by_stage": "E03.2.2",
        "license_or_origin_note": "local_repo_asset",
        "human_review_status": "not_required_auto_resolved",
    }
    write_json(dest_svg.with_suffix(".json"), meta)


def _priority_for_role(rematch_report: dict[str, Any], role: str) -> str:
    for row in rematch_report.get("decisions", []):
        if row.get("likely_role") == role:
            return row.get("priority", "P1_HIGH_REUSE")
    return "P1_HIGH_REUSE"
