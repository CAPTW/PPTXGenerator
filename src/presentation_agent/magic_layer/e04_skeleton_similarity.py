"""Detect repeated visual skeletons in the E04 source-bound deck."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e04_r2_art_direction import load_e04_r2_art_direction_plan


def build_skeleton_similarity_report(e04_root: str | Path) -> dict[str, Any]:
    root = Path(e04_root)
    art_plan = load_e04_r2_art_direction_plan(root)
    if art_plan:
        return _from_art_direction_plan(art_plan)
    blueprints = _read_json(root / "slide_blueprint_v1.json")
    rows = []
    groups: dict[str, list[str]] = defaultdict(list)
    for slide in blueprints.get("slides", []):
        signature = _body_composition_signature(slide["archetype_id"])
        groups[signature].append(slide["slide_id"])
        rows.append(
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "archetype_id": slide["archetype_id"],
                "body_composition_signature": signature,
                "card_like_body": signature == "top_title_card_row_footer",
            }
        )
    most_common_count = max((len(value) for value in groups.values()), default=0)
    ratio = most_common_count / max(1, len(rows))
    collapsed = [row for row in rows if row["card_like_body"]]
    failures = []
    if ratio > 0.40:
        failures.append("more than 40% of slides share a near-identical body composition")
    collapsed_arches = {row["archetype_id"] for row in collapsed}
    if {"process_flow", "timeline_roadmap", "evidence_overview"} & collapsed_arches and len(collapsed) >= 5:
        failures.append("process/timeline/evidence/card slides visually collapse into a repeated card-row skeleton")
    return {
        "schema_name": "skeleton_similarity_report",
        "status": "failed" if failures else "passed",
        "slide_count": len(rows),
        "near_identical_body_composition_ratio": round(ratio, 4),
        "max_shared_skeleton_slide_count": most_common_count,
        "collapsed_card_like_slide_count": len(collapsed),
        "body_composition_groups": {key: value for key, value in sorted(groups.items())},
        "slide_skeletons": rows,
        "failures": failures,
        "canva_parity_claimed": False,
    }


def _from_art_direction_plan(art_plan: dict[str, Any]) -> dict[str, Any]:
    rows = []
    groups: dict[str, list[str]] = defaultdict(list)
    for slide in art_plan.get("slides", []):
        signature = slide["composition_signature"]
        groups[signature].append(slide["slide_id"])
        rows.append(
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "archetype_id": slide["archetype_id"],
                "body_composition_signature": signature,
                "rhythm": slide["rhythm"],
                "card_like_body": signature == "top_title_card_row_footer",
            }
        )
    most_common_count = max((len(value) for value in groups.values()), default=0)
    ratio = most_common_count / max(1, len(rows))
    failures = []
    if ratio > 0.40:
        failures.append("more than 40% of slides share a near-identical body composition")
    return {
        "schema_name": "skeleton_similarity_report",
        "status": "failed" if failures else "passed",
        "slide_count": len(rows),
        "near_identical_body_composition_ratio": round(ratio, 4),
        "max_shared_skeleton_slide_count": most_common_count,
        "collapsed_card_like_slide_count": sum(1 for row in rows if row["card_like_body"]),
        "body_composition_groups": {key: value for key, value in sorted(groups.items())},
        "slide_skeletons": rows,
        "failures": failures,
        "art_direction_plan_used": True,
        "canva_parity_claimed": False,
    }


def _body_composition_signature(archetype_id: str) -> str:
    if archetype_id == "cover_hero":
        return "hero_visual_anchor"
    if archetype_id == "visual_toc":
        return "navigation_card_map"
    if archetype_id in {"comparison_matrix", "table_heavy"}:
        return "dense_table_matrix"
    if archetype_id == "data_dashboard":
        return "kpi_chart_dashboard"
    if archetype_id in {"standard_content", "evidence_overview", "card_grid", "methodology_framework", "process_flow", "timeline_roadmap"}:
        return "top_title_card_row_footer"
    if archetype_id == "section_divider":
        return "section_marker_panel"
    return "generic_content"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
