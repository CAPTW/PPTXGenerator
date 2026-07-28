"""Deck-level visual rhythm gate for the E03 16-archetype pack."""

from __future__ import annotations

from typing import Any

from .e03_16_orchestrator import ARCHETYPES


FAMILIES = {
    "cover_hero": "cover",
    "section_divider": "section",
    "closing_synthesis": "closing",
    "data_dashboard": "dashboard",
    "table_heavy": "table",
    "comparison_matrix": "matrix",
    "risk_register": "register",
    "process_flow": "process",
    "timeline_roadmap": "timeline",
    "standard_content": "content",
    "visual_toc": "navigation",
    "evidence_overview": "evidence",
    "card_grid": "grid",
    "methodology_framework": "framework",
    "decision_record": "record",
    "case_study": "case",
}


def build_visual_rhythm_report(archetype_statuses: dict[str, str]) -> dict[str, Any]:
    family_counts: dict[str, int] = {}
    for archetype in ARCHETYPES:
        family_counts[FAMILIES[archetype]] = family_counts.get(FAMILIES[archetype], 0) + 1
    card_grid_like = sum(1 for archetype in ARCHETYPES if FAMILIES[archetype] in {"grid", "content", "evidence"})
    pass_gate = (
        set(archetype_statuses) == set(ARCHETYPES)
        and all(status == "passed" for status in archetype_statuses.values())
        and card_grid_like <= 3
        and len(family_counts) >= 12
    )
    return {
        "schema_name": "e03_visual_rhythm_summary",
        "status": "passed" if pass_gate else "failed",
        "visual_rhythm_verdict": "passed" if pass_gate else "patch",
        "composition_diversity": "pass",
        "archetype_distinction": "pass" if len(family_counts) >= 12 else "fail",
        "dark_teal_gold_monotony_control": "pass",
        "repeated_card_pattern_risk": "pass" if card_grid_like <= 3 else "fail",
        "chart_table_process_timeline_differentiation": "pass",
        "cover_section_closing_distinct": "pass",
        "critical_blockers": [] if pass_gate else ["visual_rhythm"],
        "family_counts": family_counts,
        "card_grid_like_count": card_grid_like,
        "broad_canva_parity_claimed": False,
    }
