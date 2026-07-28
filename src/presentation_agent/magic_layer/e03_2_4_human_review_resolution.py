"""Resolve E03.2.4 human review annotations."""

from __future__ import annotations

from typing import Any


AUTHOR_DECISIONS = {"author_manual_svg_from_crop", "adjust_crop_then_author_svg"}
NONBLOCKING_DECISIONS = {"reject_not_icon", "mark_decorative_optional", "defer_not_required_for_e03_3"}


def resolve_human_review(review_queue: dict[str, Any], annotations: list[dict[str, Any]] | None) -> dict[str, Any]:
    items = review_queue.get("items", [])
    annotations_by_id = {row.get("review_id"): row for row in annotations or []}
    resolved = []
    approved_for_authoring = []
    unresolved = []
    for item in items:
        annotation = annotations_by_id.get(item["review_id"])
        if annotation is None:
            unresolved.append(item)
            continue
        decision = annotation["decision"]
        merged = {**item, **annotation, "resolution_status": "resolved"}
        resolved.append(merged)
        if decision in AUTHOR_DECISIONS:
            approved_for_authoring.append(merged)
    unresolved_p0 = sum(1 for row in unresolved if str(row.get("priority", "")).startswith("P0"))
    unresolved_p1 = sum(1 for row in unresolved if str(row.get("priority", "")).startswith("P1"))
    status = "passed" if not unresolved else "blocked"
    return {
        "schema_name": "human_review_resolution_report",
        "status": status,
        "human_annotations_present": annotations is not None,
        "human_review_required_count": len(items),
        "resolved_count": len(resolved),
        "approved_for_authoring_count": len(approved_for_authoring),
        "unresolved_p0_count": unresolved_p0,
        "unresolved_p1_count": unresolved_p1,
        "resolved_items": resolved,
        "approved_for_authoring": approved_for_authoring,
        "unresolved_items": unresolved,
    }
