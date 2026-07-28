"""Human review workbench manifest builder for ambiguous icon clusters."""

from __future__ import annotations

from typing import Any


ALLOWED_DECISIONS = ["accept_library_match", "generate_svg", "reject_not_icon", "decorative_optional", "adjust_crop"]


def build_human_review_workbench(clusters: dict[str, Any], annotations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    annotations_by_id = {row.get("review_id"): row for row in annotations or []}
    review_rows = []
    template = []
    for cluster in clusters.get("clusters", []):
        if cluster.get("review_status") != "review_required":
            continue
        if not str(cluster.get("priority", "")).startswith(("P0", "P1")):
            continue
        representative = cluster.get("representative_icon", {})
        review_id = cluster["cluster_id"]
        annotation = annotations_by_id.get(review_id)
        row = {
            "review_id": review_id,
            "cluster_id": cluster["cluster_id"],
            "archetype_id": representative.get("archetype_id"),
            "context_crop": representative.get("context_crop_path"),
            "raw_crop": representative.get("crop_path"),
            "glyph_only_crop": representative.get("glyph_crop_path"),
            "proposed_role": cluster["likely_role"],
            "proposed_action": "generate_svg" if cluster.get("library_match_status") == "NO_MATCH" else "accept_library_match",
            "nearest_library_matches": representative.get("nearest_library_matches", []),
            "confidence": representative.get("split_confidence", 0.7),
            "recommended_decision": annotation.get("decision") if annotation else None,
            "review_status": "resolved_by_annotation" if annotation else "pending_human_review",
        }
        review_rows.append(row)
        template.append({"review_id": review_id, "decision": "accept_library_match | generate_svg | reject_not_icon | decorative_optional | adjust_crop", "role": cluster["likely_role"], "notes": "", "adjusted_bbox_px": None})
    unresolved_p0 = sum(1 for row in review_rows if row["review_status"] != "resolved_by_annotation" and _priority_for(row, clusters).startswith("P0"))
    unresolved_p1 = sum(1 for row in review_rows if row["review_status"] != "resolved_by_annotation" and _priority_for(row, clusters).startswith("P1"))
    resolution = {
        "schema_name": "human_review_resolution_report",
        "status": "passed" if unresolved_p0 == 0 and unresolved_p1 == 0 else "pending",
        "human_review_required_count": len(review_rows),
        "resolved_count": sum(1 for row in review_rows if row["review_status"] == "resolved_by_annotation"),
        "unresolved_p0_count": unresolved_p0,
        "unresolved_p1_count": unresolved_p1,
        "pending_p0_review_count": unresolved_p0,
        "pending_p1_review_count": unresolved_p1,
        "rows": review_rows,
    }
    return {
        "schema_name": "human_review_required_icons",
        "status": resolution["status"],
        "human_review_required_count": len(review_rows),
        "icons": review_rows,
        "template": template,
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["review_id", "decision", "role"],
                "properties": {
                    "review_id": {"type": "string"},
                    "decision": {"enum": ALLOWED_DECISIONS},
                    "role": {"type": "string"},
                    "notes": {"type": "string"},
                    "adjusted_bbox_px": {"type": ["array", "null"]},
                },
            },
        },
        "resolution_report": resolution,
    }


def _priority_for(row: dict[str, Any], clusters: dict[str, Any]) -> str:
    for cluster in clusters.get("clusters", []):
        if cluster["cluster_id"] == row["cluster_id"]:
            return cluster.get("priority", "")
    return ""
