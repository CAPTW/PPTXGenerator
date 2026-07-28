"""Patch planner for E04.2 dense slide polish."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.presentation_agent.magic_layer.e04_2_dense_readability_policy import TARGET_SLIDES


def build_e04_2_patch_plan(e05_patch_queue: dict[str, Any]) -> dict[str, Any]:
    by_slide: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in e05_patch_queue.get("items", []):
        slide_number = item.get("slide_number")
        if slide_number in TARGET_SLIDES:
            by_slide[int(slide_number)].append(item)
    slide_plans = []
    for slide_number, archetype_id in TARGET_SLIDES.items():
        items = by_slide.get(slide_number, [])
        slide_plans.append(
            {
                "slide_number": slide_number,
                "archetype_id": archetype_id,
                "patch_item_count": len(items),
                "patch_ids": [item.get("patch_id") for item in items],
                "actions": [
                    "raise_visible_dense_text_to_at_least_6_2pt",
                    "raise_dense_header_text_to_at_least_7pt",
                    "preserve_editable_text_shapes",
                    "preserve_source_citation_slot_ledgers",
                    "preserve_icon_v7_1_shapes_and_visibility",
                ],
            }
        )
    return {
        "schema_name": "e04_2_patch_plan",
        "status": "ready",
        "target_slides": list(TARGET_SLIDES),
        "total_patch_items": sum(len(items) for items in by_slide.values()),
        "slide_plans": slide_plans,
    }

