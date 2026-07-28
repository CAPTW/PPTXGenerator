"""Slide-level visual acceptance matrix for E06.4.1."""

from __future__ import annotations

from typing import Any


ARCHETYPES = [
    "cover_hero",
    "visual_toc",
    "section_divider",
    "standard_content",
    "evidence_overview",
    "card_grid",
    "methodology_framework",
    "process_flow",
    "comparison_matrix",
    "data_dashboard",
    "table_heavy",
    "timeline_roadmap",
    "decision_record",
    "risk_register",
    "case_study",
    "closing_synthesis",
]

TARGET_SLIDES = {2, 9, 10, 11, 14}


def build_slide_level_visual_acceptance_matrix() -> dict[str, Any]:
    rows = []
    for idx, archetype in enumerate(ARCHETYPES, start=1):
        if idx in TARGET_SLIDES:
            rows.append(_target_row(idx, archetype))
        else:
            rows.append(
                {
                    "slide_number": idx,
                    "archetype_id": archetype,
                    "accepted_source": "accept_e06_2_1",
                    "materially_improved": False,
                    "requires_manual_patch": False,
                    "e06_3_clearly_better_than_e06_2_1": False,
                    "e06_4_clearly_better_than_e06_2_1": False,
                    "e06_3_regresses": False,
                    "e06_4_regresses": False,
                    "reason": "Non-target slide: preserve E06.2.1 because later variants do not demonstrate necessary visual improvement.",
                }
            )
    return {
        "schema_name": "slide_level_visual_acceptance_matrix",
        "status": "passed",
        "slide_count": len(rows),
        "rows": rows,
        "accepted_source_counts": _counts(rows),
        "materially_improved_count": sum(1 for row in rows if row["materially_improved"]),
        "requires_manual_patch_count": sum(1 for row in rows if row["requires_manual_patch"]),
    }


def _target_row(slide_number: int, archetype: str) -> dict[str, Any]:
    guidance = {
        2: "E06.3 darkens cards; E06.4 returns closer to baseline but does not clearly outperform E06.2.1 at contact-sheet scale.",
        9: "E06.4 spacing changes are visible but status colors appear flattened; baseline preserves semantic color cues better.",
        10: "E06.4 avoids the E06.3 dark chart regression but remains visually close to the E06.2.1 baseline.",
        11: "E06.4 row/status emphasis changes are not clearly better and may reduce color-coded status meaning.",
        14: "E06.4 risk/status chips are darker but semantic color differentiation is weakened versus baseline.",
    }
    return {
        "slide_number": slide_number,
        "archetype_id": archetype,
        "accepted_source": "accept_e06_2_1",
        "materially_improved": False,
        "requires_manual_patch": False,
        "e06_3_clearly_better_than_e06_2_1": False,
        "e06_4_clearly_better_than_e06_2_1": False,
        "e06_3_regresses": slide_number in {2, 10},
        "e06_4_regresses": slide_number in {9, 11, 14},
        "reason": guidance[slide_number],
    }


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"accept_e06_2_1": 0, "accept_e06_3": 0, "accept_e06_4": 0, "requires_manual_patch": 0}
    for row in rows:
        counts[row["accepted_source"]] += 1
    return counts
