"""Evaluate deck-level slide rhythm for the E04 design quality gate."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e04_r2_art_direction import load_e04_r2_art_direction_plan


def build_slide_rhythm_report(e04_root: str | Path, skeleton_report: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(e04_root)
    art_plan = load_e04_r2_art_direction_plan(root)
    blueprints = _read_json(root / "slide_blueprint_v1.json")
    art_by_slide = {slide["slide_id"]: slide for slide in art_plan.get("slides", [])} if art_plan else {}
    skeleton_by_slide = {
        row["slide_id"]: row
        for row in (skeleton_report or {}).get("slide_skeletons", [])
    }
    rows = []
    for slide in blueprints.get("slides", []):
        rhythm = art_by_slide.get(slide["slide_id"], {}).get("rhythm") or _rhythm_for(slide["archetype_id"])
        skeleton = skeleton_by_slide.get(slide["slide_id"], {})
        equal_weight_card = skeleton.get("body_composition_signature") == "top_title_card_row_footer" and not art_by_slide
        rows.append(
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "archetype_id": slide["archetype_id"],
                "rhythm": rhythm,
                "equal_weight_card_rhythm": bool(equal_weight_card),
            }
        )
    rhythm_counts = Counter(row["rhythm"] for row in rows)
    equal_weight_count = sum(1 for row in rows if row["equal_weight_card_rhythm"])
    required = {"hero/opening", "navigation", "evidence/problem", "framework/process", "dense data/table", "roadmap/action"}
    present = set(rhythm_counts)
    failures = []
    if not required.issubset(present):
        failures.append("one or more required deck rhythms are absent")
    if equal_weight_count >= 5:
        failures.append("too many slides read as equal-weight content cards")
    return {
        "schema_name": "slide_rhythm_report",
        "status": "failed" if failures else "passed",
        "slide_count": len(rows),
        "required_rhythms": sorted(required),
        "required_rhythms_present": sorted(present & required),
        "missing_required_rhythms": sorted(required - present),
        "rhythm_counts": dict(sorted(rhythm_counts.items())),
        "equal_weight_card_rhythm_count": equal_weight_count,
        "slides": rows,
        "failures": failures,
        "canva_parity_claimed": False,
    }


def _rhythm_for(archetype_id: str) -> str:
    if archetype_id == "cover_hero":
        return "hero/opening"
    if archetype_id == "visual_toc":
        return "navigation"
    if archetype_id in {"standard_content", "evidence_overview", "card_grid", "section_divider"}:
        return "evidence/problem"
    if archetype_id in {"methodology_framework", "process_flow"}:
        return "framework/process"
    if archetype_id in {"comparison_matrix", "data_dashboard", "table_heavy"}:
        return "dense data/table"
    if archetype_id == "timeline_roadmap":
        return "roadmap/action"
    return "content"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
