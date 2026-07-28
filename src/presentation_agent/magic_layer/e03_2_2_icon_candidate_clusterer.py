"""Cluster cleaned icon candidates to reduce review burden."""

from __future__ import annotations

from typing import Any


def cluster_icon_candidates(glyph_manifest: dict[str, Any], rematch_report: dict[str, Any] | None = None) -> dict[str, Any]:
    rematch_by_icon = {row["icon_id"]: row for row in (rematch_report or {}).get("decisions", [])}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for icon in glyph_manifest.get("icons", []):
        grouped.setdefault(icon["likely_role"], []).append(icon)
    clusters = []
    for idx, (role, members) in enumerate(sorted(grouped.items()), start=1):
        representative = members[0]
        rematch = rematch_by_icon.get(representative["icon_id"], {})
        library_status = rematch.get("classification") or "PENDING_REMATCH"
        review_status = "auto_accepted" if library_status in {"EXACT_LIBRARY_MATCH", "SHAPE_EQUIVALENT_LIBRARY_MATCH", "ACCEPTABLE_LIBRARY_ALIAS_MATCH", "GENERATED_OBSERVED_SVG_V2"} else "review_required"
        clusters.append(
            {
                "cluster_id": f"cluster_{idx:03d}_{role}",
                "likely_role": role,
                "priority": _highest_priority(members),
                "representative_icon": representative,
                "member_count": len(members),
                "member_icon_ids": [member["icon_id"] for member in members],
                "archetypes": sorted({member.get("archetype_id", "unknown") for member in members}),
                "library_match_status": library_status,
                "review_status": review_status,
                "review_resolution_scope": "cluster",
            }
        )
    return {
        "schema_name": "icon_candidate_clusters",
        "status": "passed",
        "cluster_count": len(clusters),
        "clusters": clusters,
    }


def _highest_priority(members: list[dict[str, Any]]) -> str:
    order = {"P0_REQUIRED_SEMANTIC": 0, "P1_HIGH_REUSE": 1, "P2_CONTEXTUAL": 2, "P3_DECORATIVE_OR_OPTIONAL": 3}
    return min((member.get("priority", "P3_DECORATIVE_OR_OPTIONAL") for member in members), key=lambda value: order.get(value, 9))
