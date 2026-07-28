"""Art-direction-aware E04-R2 layout selector."""

from __future__ import annotations

from collections import Counter
from typing import Any


def select_layouts_r2(blueprints: dict[str, Any], deck_art_direction_plan: dict[str, Any]) -> dict[str, Any]:
    art_by_slide = {slide["slide_id"]: slide for slide in deck_art_direction_plan["slides"]}
    selections = []
    for slide in blueprints.get("slides", []):
        art = art_by_slide[slide["slide_id"]]
        selections.append(
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "selected_archetype": slide["archetype_id"],
                "layout_id": slide["archetype_id"],
                "composition_variant": art["composition_variant"],
                "reason": f"selected to support {art['focal_object']}",
                "focal_object": art["focal_object"],
                "visual_rhythm_role": art["rhythm_position"],
                "source_content_fit": art["source_content_interpretation_goal"],
                "rejected_alternatives": ["generic_card_grid", "top_left_title_card_row_footer"],
                "risk": "low" if art["focal_object_score"] >= 0.70 else "medium",
                "patch_notes": "art direction applied before slot binding",
            }
        )
    counts = Counter(row["composition_variant"] for row in selections)
    max_reuse = max(counts.values(), default=0)
    return {
        "schema_name": "layout_selection_report_r2",
        "status": "passed" if max_reuse <= 3 else "failed",
        "selection_count": len(selections),
        "composition_variant_count": len(counts),
        "max_reused_composition_count": max_reuse,
        "selections": selections,
        "canva_parity_claimed": False,
    }


def layout_selection_report_r2_markdown(report: dict[str, Any]) -> str:
    lines = ["# Layout Selection Report R2", "", f"- Status: `{report['status']}`", f"- Composition variants: `{report['composition_variant_count']}`", "", "| Slide | Archetype | Variant | Focal object |", "|---|---|---|---|"]
    for row in report["selections"]:
        lines.append(f"| {row['slide_number']} | `{row['selected_archetype']}` | `{row['composition_variant']}` | {row['focal_object']} |")
    return "\n".join(lines)
