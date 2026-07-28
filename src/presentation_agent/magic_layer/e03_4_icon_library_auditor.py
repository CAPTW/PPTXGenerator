"""Audit curated Magic Layer v6 icons for the E03.4 foundation gate."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .e03_4_authored_svg_quality_gate import is_generic_placeholder_svg, primitive_count, validate_svg_text


def audit_icon_library_v6(taxonomy: dict[str, Any], v6_root: Path) -> dict[str, Any]:
    role_audits: list[dict[str, Any]] = []
    for role in taxonomy.get("roles", []):
        role_id = role["role_id"]
        svg_path = v6_root / f"{role_id}.svg"
        row = _audit_role_svg(role, svg_path)
        role_audits.append(row)

    extra_roles = sorted(path.stem for path in v6_root.glob("*.svg") if path.stem not in {row["role_id"] for row in taxonomy.get("roles", [])})
    accepted = [row for row in role_audits if row["status"] == "accepted"]
    quarantined = [row for row in role_audits if row["status"] == "quarantined"]
    missing = [row for row in role_audits if row["status"] == "missing"]
    return {
        "schema_name": "icon_library_audit_v6",
        "status": "passed" if role_audits else "failed",
        "v6_root": v6_root.as_posix(),
        "taxonomy_role_count": len(taxonomy.get("roles", [])),
        "accepted_v6_icon_count": len(accepted),
        "quarantined_icon_count": len(quarantined),
        "missing_icon_count": len(missing),
        "extra_v6_role_count": len(extra_roles),
        "extra_v6_roles": extra_roles,
        "role_audits": role_audits,
        "role_audits_by_role": {row["role_id"]: row for row in role_audits},
        "quarantined_svg_paths": [row["svg_path"] for row in quarantined if row.get("svg_path")],
        "generic_placeholder_p0_count": sum(
            1 for row in quarantined if row.get("priority") == "P0_REQUIRED_SEMANTIC" and row.get("placeholder_like")
        ),
        "semantic_raster_icon_count": 0,
    }


def build_icon_role_gap_matrix(taxonomy: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    role_audits = audit.get("role_audits_by_role", {})
    for role in taxonomy.get("roles", []):
        role_id = role["role_id"]
        audit_row = role_audits.get(role_id, {"status": "missing", "quality_failures": ["missing_svg"]})
        if audit_row["status"] == "accepted":
            status = "accepted_v6"
            action = "use_curated_v6"
        elif audit_row["status"] == "missing":
            status = "requires_manual_svg"
            action = "author_clean_svg_v7"
        else:
            status = "requires_manual_svg"
            action = "quarantine_and_author_clean_svg_v7"
        rows.append(
            {
                "role_id": role_id,
                "priority": role["priority"],
                "family": role["family"],
                "status": status,
                "reason": ", ".join(audit_row.get("quality_failures", [])) or audit_row["status"],
                "candidate_source": audit_row.get("svg_path"),
                "quality_score": audit_row.get("quality_score", 0.0),
                "distinctiveness_score": 1.0 if status == "accepted_v6" else 0.0,
                "legibility_score": 1.0 if status == "accepted_v6" else 0.0,
                "action": action,
            }
        )
    unresolved_p0 = [row for row in rows if row["priority"] == "P0_REQUIRED_SEMANTIC" and row["status"] != "accepted_v6"]
    unresolved_p1 = [row for row in rows if row["priority"] == "P1_HIGH_REUSE" and row["status"] != "accepted_v6"]
    return {
        "schema_name": "icon_role_gap_matrix",
        "status": "passed",
        "role_count": len(rows),
        "accepted_v6_count": sum(row["status"] == "accepted_v6" for row in rows),
        "requires_manual_svg_count": sum(row["status"] == "requires_manual_svg" for row in rows),
        "unresolved_p0_count": len(unresolved_p0),
        "unresolved_p1_count": len(unresolved_p1),
        "roles": rows,
        "roles_by_role": {row["role_id"]: row for row in rows},
    }


def _audit_role_svg(role: dict[str, Any], svg_path: Path) -> dict[str, Any]:
    role_id = role["role_id"]
    if not svg_path.exists():
        return {
            "role_id": role_id,
            "priority": role["priority"],
            "family": role["family"],
            "status": "missing",
            "svg_path": svg_path.as_posix(),
            "quality_failures": ["missing_svg"],
            "placeholder_like": False,
            "quality_score": 0.0,
        }
    text = svg_path.read_text(encoding="utf-8")
    failures = validate_svg_text(text, role_id=role_id)
    placeholder = is_generic_placeholder_svg(text, role_id=role_id)
    if placeholder and "generic_placeholder_shape" not in failures:
        failures.append("generic_placeholder_shape")
    status = "accepted" if not failures else "quarantined"
    return {
        "role_id": role_id,
        "priority": role["priority"],
        "family": role["family"],
        "status": status,
        "svg_path": svg_path.as_posix(),
        "sha256": hashlib.sha256(svg_path.read_bytes()).hexdigest(),
        "quality_failures": failures,
        "placeholder_like": placeholder,
        "primitive_count": primitive_count(text),
        "has_current_color": "currentColor" in text,
        "quality_score": 1.0 if status == "accepted" else 0.0,
    }
