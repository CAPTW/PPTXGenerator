"""Evaluate visual hierarchy depth in the E04 source-bound deck."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from src.presentation_agent.magic_layer.e04_r2_art_direction import load_e04_r2_art_direction_plan


PASS_THRESHOLD = 0.62


def build_visual_hierarchy_report(e04_root: str | Path) -> dict[str, Any]:
    root = Path(e04_root)
    art_plan = load_e04_r2_art_direction_plan(root)
    if art_plan:
        return _from_art_direction_plan(art_plan)
    blueprints = _read_json(root / "slide_blueprint_v1.json")
    rows = []
    for slide in blueprints.get("slides", []):
        score, reason = _hierarchy_score(slide["archetype_id"])
        rows.append(
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "archetype_id": slide["archetype_id"],
                "visual_hierarchy_score": score,
                "hierarchy_reason": reason,
                "flat_card_hierarchy": slide["archetype_id"] in {"standard_content", "evidence_overview", "card_grid", "methodology_framework", "process_flow", "timeline_roadmap"},
            }
        )
    average = round(mean(row["visual_hierarchy_score"] for row in rows), 4) if rows else 0
    flat_count = sum(1 for row in rows if row["flat_card_hierarchy"])
    failures = []
    if average < PASS_THRESHOLD:
        failures.append("average visual hierarchy score is below the premium deck threshold")
    if flat_count >= 5:
        failures.append("too many slides rely on flat card-level hierarchy")
    return {
        "schema_name": "visual_hierarchy_report",
        "status": "failed" if failures else "passed",
        "slide_count": len(rows),
        "average_visual_hierarchy_score": average,
        "pass_threshold": PASS_THRESHOLD,
        "flat_card_hierarchy_slide_count": flat_count,
        "slides": rows,
        "failures": failures,
        "canva_parity_claimed": False,
    }


def _from_art_direction_plan(art_plan: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for slide in art_plan.get("slides", []):
        rows.append(
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "archetype_id": slide["archetype_id"],
                "visual_hierarchy_score": float(slide["visual_hierarchy_score"]),
                "hierarchy_reason": slide["layout_strategy"],
                "flat_card_hierarchy": bool(slide.get("flat_card_hierarchy", False)),
            }
        )
    average = round(mean(row["visual_hierarchy_score"] for row in rows), 4) if rows else 0
    flat_count = sum(1 for row in rows if row["flat_card_hierarchy"])
    failures = []
    if average < PASS_THRESHOLD:
        failures.append("average visual hierarchy score is below the premium deck threshold")
    if flat_count >= 5:
        failures.append("too many slides rely on flat card-level hierarchy")
    return {
        "schema_name": "visual_hierarchy_report",
        "status": "failed" if failures else "passed",
        "slide_count": len(rows),
        "average_visual_hierarchy_score": average,
        "pass_threshold": PASS_THRESHOLD,
        "flat_card_hierarchy_slide_count": flat_count,
        "slides": rows,
        "failures": failures,
        "art_direction_plan_used": True,
        "canva_parity_claimed": False,
    }


def _hierarchy_score(archetype_id: str) -> tuple[float, str]:
    scores = {
        "cover_hero": (0.70, "hero field establishes a primary anchor"),
        "visual_toc": (0.58, "navigation system exists but reads as similar cards"),
        "section_divider": (0.46, "section marker does not strongly break deck rhythm"),
        "standard_content": (0.34, "three cards share equal visual weight"),
        "evidence_overview": (0.38, "evidence cards lack a dominant claim/proof hierarchy"),
        "card_grid": (0.32, "grid cards are visually equivalent"),
        "methodology_framework": (0.42, "framework stages read as content cards"),
        "process_flow": (0.40, "flow emphasis is too weak relative to equal nodes"),
        "comparison_matrix": (0.68, "table/matrix is the main information object"),
        "data_dashboard": (0.74, "chart and KPI field carry the slide"),
        "table_heavy": (0.70, "table is the primary object with header/body structure"),
        "timeline_roadmap": (0.42, "timeline rail is present but cards remain dominant"),
    }
    return scores.get(archetype_id, (0.5, "generic content hierarchy"))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
