"""Summarize P0/P1 role resolution after E03.2.4A review application."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def resolve_rejected_required_roles_from_curated(review_resolution: dict[str, Any], curated_roots: list[Path], forbidden_svg_paths: set[str]) -> dict[str, Any]:
    forbidden = {_safe_resolve(Path(path)) for path in forbidden_svg_paths if path}
    resolved_items = list(review_resolution.get("resolved_items", []))
    unresolved_items: list[dict[str, Any]] = []
    approved_library_matches = list(review_resolution.get("approved_library_matches", []))
    for row in review_resolution.get("unresolved_items", []):
        if row.get("decision") != "reject_not_icon" or not _is_required(row):
            unresolved_items.append(row)
            continue
        role = str(row.get("role") or row.get("role_guess") or "")
        match = _find_curated_role_svg(role, curated_roots, forbidden)
        if match is None:
            unresolved_items.append({**row, "unresolved_reason": "rejected_crop_required_role_has_no_non_quarantined_curated_match"})
            continue
        resolved = {
            **row,
            "role": role,
            "source_path": match.as_posix(),
            "resolution_status": "resolved_library",
            "resolution_reason": "crop_rejected_but_required_role_resolved_from_curated_library",
        }
        resolved_items.append(resolved)
        approved_library_matches.append(resolved)
    unresolved_p0 = sum(1 for row in unresolved_items if str(row.get("priority", "")).startswith("P0"))
    unresolved_p1 = sum(1 for row in unresolved_items if str(row.get("priority", "")).startswith("P1"))
    return {
        **review_resolution,
        "status": "passed" if not unresolved_items else "blocked",
        "resolved_count": len(resolved_items),
        "approved_library_match_count": len(approved_library_matches),
        "approved_library_matches": approved_library_matches,
        "resolved_items": resolved_items,
        "unresolved_items": unresolved_items,
        "unresolved_p0_count": unresolved_p0,
        "unresolved_p1_count": unresolved_p1,
    }


def build_p0_p1_role_resolution_report(review_resolution: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in review_resolution.get("resolved_items", []):
        status = _normalized_status(str(row.get("resolution_status") or "resolved"))
        rows.append(
            {
                "review_id": row.get("review_id"),
                "role": row.get("role") or row.get("role_guess"),
                "priority": row.get("priority"),
                "status": status,
                "source_path": row.get("source_path") or row.get("svg_path"),
                "reason": row.get("decision"),
                "confidence": 0.9 if status.startswith("resolved") else 0.7,
                "usage_contexts": row.get("member_icon_ids", []),
            }
        )
    for row in review_resolution.get("unresolved_items", []):
        rows.append(
            {
                "review_id": row.get("review_id"),
                "role": row.get("role") or row.get("role_guess"),
                "priority": row.get("priority"),
                "status": "unresolved",
                "source_path": None,
                "reason": row.get("unresolved_reason"),
                "confidence": 0.0,
                "usage_contexts": row.get("member_icon_ids", []),
            }
        )
    unresolved_p0 = sum(1 for row in rows if row["status"] == "unresolved" and str(row.get("priority", "")).startswith("P0"))
    unresolved_p1 = sum(1 for row in rows if row["status"] == "unresolved" and str(row.get("priority", "")).startswith("P1"))
    return {
        "schema_name": "p0_p1_role_resolution_report",
        "status": "passed" if unresolved_p0 == 0 and unresolved_p1 == 0 else "blocked",
        "role_count": len(rows),
        "resolved_library_count": sum(1 for row in rows if row["status"] == "resolved_library"),
        "resolved_authored_svg_count": sum(1 for row in rows if row["status"] == "resolved_authored_svg"),
        "rejected_not_required_count": sum(1 for row in rows if row["status"] == "rejected_not_required"),
        "unresolved_p0_count": unresolved_p0,
        "unresolved_required_p1_count": unresolved_p1,
        "roles": rows,
    }


def _normalized_status(status: str) -> str:
    if status == "resolved_authored_svg_pending":
        return "resolved_authored_svg"
    if status in {"resolved_library", "resolved_authored_svg", "rejected_not_required"}:
        return status
    if status == "not_required_for_e03_3":
        return "rejected_not_required"
    return status


def _find_curated_role_svg(role: str, curated_roots: list[Path], forbidden: set[str]) -> Path | None:
    for root in curated_roots:
        candidate = root / f"{role}.svg"
        if candidate.exists() and _safe_resolve(candidate) not in forbidden:
            return candidate
    return None


def _safe_resolve(path: Path) -> str:
    try:
        return path.resolve().as_posix()
    except OSError:
        return path.as_posix()


def _is_required(row: dict[str, Any]) -> bool:
    return str(row.get("priority", "")).startswith(("P0", "P1"))
