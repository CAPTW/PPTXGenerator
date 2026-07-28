"""Evaluate whether each E04 slide has a clear primary focal object."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e04_r2_art_direction import load_e04_r2_art_direction_plan


def build_focal_object_report(e04_root: str | Path) -> dict[str, Any]:
    root = Path(e04_root)
    art_plan = load_e04_r2_art_direction_plan(root)
    if art_plan:
        return _from_art_direction_plan(art_plan)
    blueprints = _read_json(root / "slide_blueprint_v1.json")
    rows = []
    for slide in blueprints.get("slides", []):
        focal = _focal_assessment(slide["archetype_id"])
        rows.append(
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "archetype_id": slide["archetype_id"],
                **focal,
            }
        )
    weak = [row for row in rows if row["focal_object_status"] != "passed"]
    return {
        "schema_name": "focal_object_report",
        "status": "failed" if weak else "passed",
        "slide_count": len(rows),
        "weak_focal_object_count": len(weak),
        "weak_focal_object_slides": weak,
        "slides": rows,
        "failures": ["one or more slides lack a strong primary focal object"] if weak else [],
        "canva_parity_claimed": False,
    }


def _from_art_direction_plan(art_plan: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for slide in art_plan.get("slides", []):
        score = float(slide["focal_object_score"])
        rows.append(
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "archetype_id": slide["archetype_id"],
                "primary_focal_object": slide["primary_focal_object"],
                "focal_object_score": score,
                "focal_object_status": "passed" if score >= 0.68 else "failed",
                "expected_focal_object": slide["layout_strategy"],
            }
        )
    weak = [row for row in rows if row["focal_object_status"] != "passed"]
    return {
        "schema_name": "focal_object_report",
        "status": "failed" if weak else "passed",
        "slide_count": len(rows),
        "weak_focal_object_count": len(weak),
        "weak_focal_object_slides": weak,
        "slides": rows,
        "failures": ["one or more slides lack a strong primary focal object"] if weak else [],
        "art_direction_plan_used": True,
        "canva_parity_claimed": False,
    }


def _focal_assessment(archetype_id: str) -> dict[str, Any]:
    strong = {
        "cover_hero": ("hero visual field", 0.72, "passed"),
        "visual_toc": ("navigation map", 0.68, "passed"),
        "comparison_matrix": ("native comparison matrix", 0.70, "passed"),
        "data_dashboard": ("native chart and KPI field", 0.76, "passed"),
        "table_heavy": ("native table", 0.72, "passed"),
    }
    weak = {
        "standard_content": ("three equal cards", 0.38, "failed"),
        "evidence_overview": ("equal evidence cards", 0.40, "failed"),
        "card_grid": ("repeated cards", 0.35, "failed"),
        "methodology_framework": ("framework cards without strong diagram emphasis", 0.43, "failed"),
        "process_flow": ("process labels do not dominate as a flow object", 0.42, "failed"),
        "timeline_roadmap": ("roadmap cards overpower timeline rail", 0.44, "failed"),
        "section_divider": ("section marker present but not a strong divider", 0.48, "warning"),
    }
    label, score, status = strong.get(archetype_id) or weak.get(archetype_id) or ("content group", 0.5, "warning")
    return {
        "primary_focal_object": label,
        "focal_object_score": score,
        "focal_object_status": status,
        "expected_focal_object": _expected_focal_object(archetype_id),
    }


def _expected_focal_object(archetype_id: str) -> str:
    return {
        "cover_hero": "hero visual or strong title/visual anchor",
        "visual_toc": "map/sequence system",
        "standard_content": "claim/evidence hierarchy",
        "evidence_overview": "claim/proof/source hierarchy",
        "card_grid": "structured content system with hierarchy",
        "methodology_framework": "diagram or framework emphasis",
        "process_flow": "flow emphasis",
        "comparison_matrix": "matrix as main information object",
        "data_dashboard": "chart/data focal area",
        "table_heavy": "readable table as main information object",
        "timeline_roadmap": "timeline rail and milestones",
    }.get(archetype_id, "clear primary focal object")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
