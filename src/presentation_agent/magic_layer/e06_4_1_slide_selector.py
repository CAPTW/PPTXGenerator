"""Slide selection and rollback decisions for E06.4.1."""

from __future__ import annotations

from typing import Any


def build_rollback_decision_report(matrix: dict[str, Any]) -> dict[str, Any]:
    rows = matrix.get("rows", [])
    rolled_back = [
        {
            "slide_number": row["slide_number"],
            "archetype_id": row["archetype_id"],
            "from_candidate": "E06.4",
            "selected_source": row["accepted_source"],
            "reason": row["reason"],
        }
        for row in rows
        if row["slide_number"] in {2, 9, 10, 11, 14} and row["accepted_source"] != "accept_e06_4"
    ]
    return {
        "schema_name": "rollback_decision_report",
        "status": "passed",
        "rolled_back_from_e06_4_count": len(rolled_back),
        "rolled_back_slides": rolled_back,
    }


def build_best_slide_source_manifest(matrix: dict[str, Any]) -> dict[str, Any]:
    rows = matrix.get("rows", [])
    return {
        "schema_name": "best_slide_source_manifest",
        "status": "passed" if len(rows) == 16 and all(row["accepted_source"] != "requires_manual_patch" for row in rows) else "manual_patch_required",
        "slide_count": len(rows),
        "accepted_source_counts": matrix.get("accepted_source_counts", {}),
        "slides": [
            {
                "slide_number": row["slide_number"],
                "archetype_id": row["archetype_id"],
                "accepted_source": row["accepted_source"],
                "materially_improved": row["materially_improved"],
                "reason": row["reason"],
            }
            for row in rows
        ],
    }
