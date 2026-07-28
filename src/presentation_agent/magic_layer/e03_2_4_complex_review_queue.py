"""Build compact P0/P1 complex icon review queue."""

from __future__ import annotations

from typing import Any


EXCLUDED_ROLES = {"source"}


def build_p0_p1_complex_icon_review_queue(cluster_manifest: dict[str, Any], quarantine_report: dict[str, Any]) -> dict[str, Any]:
    quarantined_icon_ids = {row.get("icon_id") for row in quarantine_report.get("quarantined_svgs", [])}
    quarantined_roles = set(quarantine_report.get("quarantined_roles", []))
    items = []
    for cluster in cluster_manifest.get("clusters", []):
        role = cluster.get("likely_role")
        priority = cluster.get("priority", "")
        if role in EXCLUDED_ROLES or not priority.startswith(("P0", "P1")):
            continue
        member_ids = set(cluster.get("member_icon_ids", []))
        requires_review = bool(member_ids & quarantined_icon_ids) or role in quarantined_roles or cluster.get("requires_vectorization")
        if not requires_review:
            continue
        representative = cluster.get("representative_icon", {})
        review_id = f"review_{cluster['cluster_id']}"
        items.append(
            {
                "review_id": review_id,
                "cluster_id": cluster["cluster_id"],
                "archetype_id": representative.get("archetype_id"),
                "role_guess": role,
                "priority": priority,
                "context_crop": representative.get("context_crop_path"),
                "raw_crop": representative.get("crop_path"),
                "cleaned_glyph_crop": representative.get("normalized_256_path") or representative.get("normalized_crop_path"),
                "current_svg_result": representative.get("selected_svg_path"),
                "nearest_library_match": representative.get("matched_svg_path"),
                "why_review_required": "quarantined_or_complex_p0_p1_icon_cluster",
                "recommended_action": "author_manual_svg_from_crop" if role in quarantined_roles or member_ids & quarantined_icon_ids else "accept_existing_library_match",
                "member_icon_ids": sorted(member_ids),
            }
        )
    return {
        "schema_name": "p0_p1_complex_icon_cluster_review_queue",
        "status": "review_required" if items else "passed",
        "review_queue_count": len(items),
        "items": items,
    }


def build_human_review_annotations_template(review_queue: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "review_id": item["review_id"],
            "decision": "accept_existing_library_match | author_manual_svg_from_crop | adjust_crop_then_author_svg | reject_not_icon | mark_decorative_optional | defer_not_required_for_e03_3",
            "approved_variant": None,
            "role": item["role_guess"],
            "notes": "",
            "adjusted_bbox_px": None,
        }
        for item in review_queue.get("items", [])
    ]


def build_human_review_annotations_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["review_id", "decision", "role"],
            "properties": {
                "review_id": {"type": "string"},
                "decision": {
                    "enum": [
                        "accept_existing_library_match",
                        "author_manual_svg_from_crop",
                        "adjust_crop_then_author_svg",
                        "reject_not_icon",
                        "mark_decorative_optional",
                        "defer_not_required_for_e03_3",
                    ]
                },
                "approved_variant": {"type": ["string", "null"]},
                "role": {"type": "string"},
                "notes": {"type": "string"},
                "adjusted_bbox_px": {"type": ["array", "null"]},
            },
        },
    }
