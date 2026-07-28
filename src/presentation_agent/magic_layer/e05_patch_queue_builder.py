"""Patch queue builder for E05 product review."""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_e05_patch_queue(*, slide_matrix: dict[str, Any], reviews: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()
    for review in reviews:
        for issue in review.get("issues", []):
            slide_number = int(issue["slide_number"]) if issue.get("slide_number") else 0
            key = (slide_number, issue.get("patch_type", "product_polish"), issue.get("issue", ""))
            if key in seen:
                continue
            seen.add(key)
            items.append(_item(len(items) + 1, issue))
    for row in slide_matrix.get("rows", []):
        if row.get("severity") in {"medium", "high", "critical"}:
            issue = {
                "slide_number": row["slide_number"],
                "archetype_id": row["archetype_id"],
                "issue": row["patch_recommendation"],
                "severity": row["severity"],
                "patch_type": "visual_hierarchy_patch",
                "recommended_action": row["patch_recommendation"],
            }
            key = (int(row["slide_number"]), "visual_hierarchy_patch", row["patch_recommendation"])
            if key not in seen:
                seen.add(key)
                items.append(_item(len(items) + 1, issue))

    counts = Counter(item["severity"] for item in items)
    queue = {
        "schema_name": "e05_patch_queue",
        "status": "open" if items else "empty",
        "item_count": len(items),
        "critical_blocker_count": counts.get("critical", 0),
        "high_product_risk_count": counts.get("high", 0),
        "medium_polish_count": counts.get("medium", 0),
        "low_polish_count": counts.get("low", 0),
        "items": items,
    }
    priority = {
        "schema_name": "e05_patch_priority_matrix",
        "status": queue["status"],
        "counts": {
            "critical_blocker": queue["critical_blocker_count"],
            "high_product_risk": queue["high_product_risk_count"],
            "medium_polish": queue["medium_polish_count"],
            "low_polish": queue["low_polish_count"],
        },
        "priority_order": ["critical_blocker", "high_product_risk", "medium_polish", "low_polish"],
        "items": items,
    }
    return queue, priority


def build_e04_2_patch_plan(patch_queue: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e04_2_patch_plan",
        "status": "required" if patch_queue.get("item_count", 0) else "not_required",
        "target_stage": "E04.2_SOURCE_BOUND_PRODUCT_POLISH",
        "scope": "deterministic visual/readability polish only; no new source claims or scaleout",
        "patch_count": patch_queue.get("item_count", 0),
        "items": patch_queue.get("items", []),
    }


def _item(index: int, issue: dict[str, Any]) -> dict[str, Any]:
    severity = issue.get("severity", "medium")
    return {
        "patch_id": f"E05-PATCH-{index:03d}",
        "slide_number": issue.get("slide_number"),
        "archetype_id": issue.get("archetype_id"),
        "issue": issue.get("issue"),
        "severity": severity,
        "deterministic_patch_possible": True,
        "recommended_action": issue.get("recommended_action"),
        "patch_type": issue.get("patch_type", "visual_hierarchy_patch"),
        "expected_output_stage": "E04.2_SOURCE_BOUND_PRODUCT_POLISH",
        "blocker_for_e06": severity in {"critical", "high"} or issue.get("patch_type") in {"table_density_patch", "text_capacity_patch", "source_footer_readability_patch"},
    }

