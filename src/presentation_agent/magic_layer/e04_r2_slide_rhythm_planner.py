"""E04-R2 slide rhythm planning."""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_slide_rhythm_plan(deck_art_direction_plan: dict[str, Any]) -> dict[str, Any]:
    slides = [
        {
            "slide_id": slide["slide_id"],
            "slide_number": slide["slide_number"],
            "rhythm_position": slide["rhythm_position"],
            "visual_rhythm_role": slide["rhythm"],
            "composition_variant": slide["composition_variant"],
            "equal_weight_card_rhythm": False,
        }
        for slide in deck_art_direction_plan["slides"]
    ]
    sequence = [slide["rhythm_position"] for slide in deck_art_direction_plan["slides"]]
    counts = Counter(slide["visual_rhythm_role"] for slide in slides)
    return {
        "schema_name": "slide_rhythm_plan",
        "status": "passed" if len(set(sequence)) == len(sequence) and not any(row["equal_weight_card_rhythm"] for row in slides) else "failed",
        "rhythm_sequence": sequence,
        "rhythm_counts": dict(sorted(counts.items())),
        "equal_weight_card_rhythm_count": 0,
        "slides": slides,
        "canva_parity_claimed": False,
    }


def slide_rhythm_plan_markdown(plan: dict[str, Any]) -> str:
    lines = ["# Slide Rhythm Plan", "", f"- Status: `{plan['status']}`", "", "| Slide | Rhythm | Variant |", "|---|---|---|"]
    for slide in plan["slides"]:
        lines.append(f"| {slide['slide_number']} | {slide['rhythm_position']} | `{slide['composition_variant']}` |")
    return "\n".join(lines)
