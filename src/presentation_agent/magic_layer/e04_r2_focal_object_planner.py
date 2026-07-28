"""E04-R2 focal object planning."""

from __future__ import annotations

from typing import Any


def build_focal_object_plan(deck_art_direction_plan: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for slide in deck_art_direction_plan["slides"]:
        title_only = slide["focal_object"].strip().lower() == slide["original_title"].strip().lower()
        rows.append(
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "archetype_id": slide["archetype_id"],
                "focal_object": slide["focal_object"],
                "expected_focal_object": slide["primary_focal_object"],
                "focal_object_score": slide["focal_object_score"],
                "focal_object_is_title_only": title_only,
                "status": "failed" if title_only or slide["focal_object_score"] < 0.68 else "passed",
            }
        )
    weak = [row for row in rows if row["status"] != "passed"]
    return {
        "schema_name": "focal_object_plan",
        "status": "passed" if not weak else "failed",
        "slide_count": len(rows),
        "weak_focal_object_count": len(weak),
        "slides": rows,
        "canva_parity_claimed": False,
    }


def focal_object_plan_markdown(plan: dict[str, Any]) -> str:
    lines = ["# Focal Object Plan", "", f"- Status: `{plan['status']}`", f"- Weak focal objects: `{plan['weak_focal_object_count']}`", "", "| Slide | Focal object | Score |", "|---|---|---|"]
    for slide in plan["slides"]:
        lines.append(f"| {slide['slide_number']} | {slide['focal_object']} | `{slide['focal_object_score']}` |")
    return "\n".join(lines)
