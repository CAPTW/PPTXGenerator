"""Apply normalized E03.2.4A human review annotations."""

from __future__ import annotations

from typing import Any

from .e03_2_4a_annotation_loader import is_concrete_decision


AUTHOR_DECISIONS = {"author_manual_svg_from_crop", "adjust_crop_then_author_svg"}


def apply_human_review_annotations(
    review_queue: dict[str, Any],
    mapping_report: dict[str, Any],
    *,
    quarantined_svg_paths: set[str],
    placeholder_svg_paths: set[str],
) -> dict[str, Any]:
    items = list(review_queue.get("items") or review_queue.get("review_queue") or [])
    annotations = {row["review_id"]: row for row in mapping_report.get("normalized_annotations", [])}
    resolved: list[dict[str, Any]] = []
    approved_for_authoring: list[dict[str, Any]] = []
    approved_library_matches: list[dict[str, Any]] = []
    rejected_crops: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    rejected_quarantined = 0
    rejected_placeholder = 0

    for item in items:
        annotation = annotations.get(item["review_id"])
        decision = annotation.get("decision") if annotation else None
        role = (annotation or {}).get("role") or item.get("role_guess")
        merged = {**item, **(annotation or {}), "role": role}
        if not is_concrete_decision(decision):
            unresolved.append({**merged, "unresolved_reason": "missing_concrete_human_review_decision"})
            continue

        if decision == "accept_existing_library_match":
            source = str(annotation.get("source_path") or item.get("nearest_library_match") or item.get("current_svg_result") or "")
            if source in quarantined_svg_paths:
                rejected_quarantined += 1
                unresolved.append({**merged, "source_path": source, "unresolved_reason": "library_match_is_quarantined"})
                continue
            if source in placeholder_svg_paths:
                rejected_placeholder += 1
                unresolved.append({**merged, "source_path": source, "unresolved_reason": "library_match_is_placeholder"})
                continue
            resolved_row = {**merged, "source_path": source, "resolution_status": "resolved_library"}
            resolved.append(resolved_row)
            approved_library_matches.append(resolved_row)
            continue

        if decision in AUTHOR_DECISIONS:
            resolved_row = {**merged, "resolution_status": "resolved_authored_svg_pending"}
            resolved.append(resolved_row)
            approved_for_authoring.append(resolved_row)
            continue

        if decision == "reject_not_icon":
            rejected_crops.append({**merged, "resolution_status": "rejected_crop_not_icon"})
            if _is_required_priority(item):
                unresolved.append({**merged, "unresolved_reason": "required_role_rejected_crop_needs_alternate_resolution"})
            else:
                resolved.append({**merged, "resolution_status": "rejected_not_required"})
            continue

        if decision in {"mark_decorative_optional", "defer_not_required_for_e03_3"}:
            resolved.append({**merged, "resolution_status": "not_required_for_e03_3"})
            continue

    unresolved_p0 = sum(1 for row in unresolved if str(row.get("priority", "")).startswith("P0"))
    unresolved_p1 = sum(1 for row in unresolved if str(row.get("priority", "")).startswith("P1"))
    return {
        "schema_name": "human_review_resolution_report",
        "status": "passed" if not unresolved else "blocked",
        "human_annotations_present": bool(mapping_report.get("annotation_count")),
        "human_review_required_count": len(items),
        "resolved_count": len(resolved),
        "approved_for_authoring_count": len(approved_for_authoring),
        "approved_library_match_count": len(approved_library_matches),
        "rejected_crop_count": len(rejected_crops),
        "rejected_quarantined_match_count": rejected_quarantined,
        "rejected_placeholder_match_count": rejected_placeholder,
        "unresolved_p0_count": unresolved_p0,
        "unresolved_p1_count": unresolved_p1,
        "resolved_items": resolved,
        "approved_for_authoring": approved_for_authoring,
        "approved_library_matches": approved_library_matches,
        "rejected_crops": rejected_crops,
        "unresolved_items": unresolved,
    }


def _is_required_priority(row: dict[str, Any]) -> bool:
    return str(row.get("priority", "")).startswith(("P0", "P1"))
