"""Normalize possibly fuzzy E03.2.4A annotation review IDs to queue IDs."""

from __future__ import annotations

import re
from typing import Any

from .e03_2_4a_annotation_loader import is_concrete_decision


def normalize_review_annotations(review_queue: dict[str, Any], annotations: list[dict[str, Any]]) -> dict[str, Any]:
    items = _items(review_queue)
    by_id = {row["review_id"]: row for row in items}
    mappings: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    mapped_queue_ids: set[str] = set()
    unmapped_annotations: list[dict[str, Any]] = []

    for annotation in annotations:
        matched, method, confidence = _match_annotation(annotation, items, by_id)
        if matched is None:
            unmapped_annotations.append(annotation)
            continue
        mapped_queue_ids.add(matched["review_id"])
        normalized_row = {**annotation, "review_id": matched["review_id"], "role": annotation.get("role") or matched.get("role_guess")}
        normalized.append(normalized_row)
        mappings.append(
            {
                "input_review_id": annotation.get("review_id"),
                "matched_review_id": matched["review_id"],
                "role": normalized_row.get("role"),
                "mapping_method": method,
                "mapping_confidence": confidence,
                "decision_is_concrete": is_concrete_decision(normalized_row.get("decision")),
            }
        )

    unmapped_queue = [row for row in items if row["review_id"] not in mapped_queue_ids]
    concrete_count = sum(1 for row in normalized if is_concrete_decision(row.get("decision")))
    return {
        "schema_name": "human_review_annotation_mapping_report",
        "status": "passed" if not unmapped_queue and concrete_count else "blocked",
        "queue_count": len(items),
        "annotation_count": len(annotations),
        "mapped_count": len(mappings),
        "unmapped_queue_count": len(unmapped_queue),
        "unmapped_annotation_count": len(unmapped_annotations),
        "concrete_annotation_count": concrete_count,
        "mapping_complete": not unmapped_queue,
        "mappings": mappings,
        "normalized_annotations": normalized,
        "unmapped_queue_items": unmapped_queue,
        "unmapped_annotations": unmapped_annotations,
    }


def _match_annotation(annotation: dict[str, Any], items: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]) -> tuple[dict[str, Any] | None, str, float]:
    review_id = str(annotation.get("review_id") or "")
    if review_id in by_id:
        return by_id[review_id], "exact_review_id", 1.0

    role = str(annotation.get("role") or "").lower()
    index = _cluster_index(review_id)
    if index and role:
        for row in items:
            row_id = str(row.get("review_id") or "")
            if _cluster_index(row_id) == index and role == str(row.get("role_guess") or "").lower():
                return row, "cluster_index_and_role", 0.92

    if role:
        role_matches = [row for row in items if role == str(row.get("role_guess") or "").lower()]
        if len(role_matches) == 1:
            return role_matches[0], "unique_role", 0.75

    return None, "unmapped", 0.0


def _cluster_index(value: str) -> str | None:
    match = re.search(r"(?:cluster[_-]?)?(\d{1,3})", value)
    if not match:
        return None
    return match.group(1).zfill(3)


def _items(review_queue: dict[str, Any]) -> list[dict[str, Any]]:
    return list(review_queue.get("items") or review_queue.get("review_queue") or [])
