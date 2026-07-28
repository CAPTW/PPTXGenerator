"""Visual product review for E04.1 semantic icon micro-placement."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.presentation_agent.magic_layer.e05_product_review_rubric import SLIDE_ORDER


def review_icon_micro_placement(micro_ledger: dict[str, Any], size_ledger: dict[str, Any], visibility_report: dict[str, Any]) -> dict[str, Any]:
    rows = list(micro_ledger.get("rows", []))
    by_slide: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_slide[int(row.get("slide_number", 0))].append(row)

    slide_reviews = []
    issues = []
    for slide_number, archetype_id in enumerate(SLIDE_ORDER, start=1):
        icons = by_slide.get(slide_number, [])
        score = 4.4
        notes = []
        if not icons:
            score -= 0.2
            notes.append("no semantic icon slots on this slide")
        if any(not row.get("anchored") for row in icons):
            score = min(score, 2.0)
            notes.append("unanchored semantic icon")
        if any(row.get("raster_fallback") for row in icons):
            score = min(score, 1.0)
            notes.append("semantic icon raster fallback")
        if len(icons) >= 5:
            score -= 0.25
            notes.append("dense icon vocabulary requires visual polish review")
        if archetype_id in {"table_heavy", "risk_register"}:
            score -= 0.35
            notes.append("icons are visible but compete with dense table/register cells")
        if archetype_id in {"comparison_matrix", "data_dashboard"}:
            score -= 0.15
            notes.append("icons should remain secondary to matrix/chart data")
        score = round(max(1.0, score), 2)
        if score < 4.0:
            issues.append(
                {
                    "slide_number": slide_number,
                    "archetype_id": archetype_id,
                    "issue": "; ".join(notes),
                    "severity": "medium" if score >= 3.5 else "high",
                    "patch_type": "icon_micro_position_patch",
                    "recommended_action": "Tune icon badge scale/placement against local component density.",
                }
            )
        slide_reviews.append(
            {
                "slide_number": slide_number,
                "archetype_id": archetype_id,
                "semantic_icon_count": len(icons),
                "score": score,
                "status": "passed" if score >= 3.5 and not any(not row.get("anchored") for row in icons) else "patch_required",
                "notes": notes,
            }
        )

    verdict = "passed" if visibility_report.get("status") == "passed" and micro_ledger.get("unanchored_semantic_icon_count") == 0 else "failed"
    if issues:
        verdict = "patch_recommended" if verdict == "passed" else verdict
    return {
        "schema_name": "e05_icon_micro_placement_review",
        "status": verdict,
        "semantic_icon_count": len(rows),
        "anchored_semantic_icon_count": micro_ledger.get("anchored_semantic_icon_count", 0),
        "unanchored_semantic_icon_count": micro_ledger.get("unanchored_semantic_icon_count", 0),
        "invisible_icon_count": visibility_report.get("invisible_icon_count", 0),
        "blank_icon_bbox_count": visibility_report.get("blank_icon_bbox_count", 0),
        "semantic_raster_icon_count": micro_ledger.get("semantic_raster_icon_count", 0),
        "size_token_status": size_ledger.get("status"),
        "slide_reviews": slide_reviews,
        "issues": issues,
    }

