"""Deck-level art direction for E04H source-bound hybrid deck."""

from __future__ import annotations

from typing import Any


RHYTHM = [
    "hero/opening",
    "navigation",
    "problem/failure",
    "evidence/source",
    "framework/process",
    "workflow",
    "operating cadence",
    "comparison/matrix",
    "data/dashboard",
    "table/governance",
    "roadmap/action",
    "closing/recommendation",
]


def build_e04h_slide_art_direction_plan(source_artifacts: dict[str, Any], layout_report: dict[str, Any]) -> dict[str, Any]:
    by_slide = {row["slide_id"]: row for row in layout_report.get("selections", [])}
    slides = []
    for index, slide in enumerate(source_artifacts.get("slides", [])):
        selected = by_slide[slide["slide_id"]]["selected_reference_id"]
        slides.append(
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "narrative_role": _narrative_role(index, selected),
                "selected_reference_id": selected,
                "focal_object": _focal_object(selected),
                "visual_backplate_usage": "retain bounded nonsemantic hybrid backplates behind source-bound semantic overlays",
                "semantic_content_priority": ["title", "primary_claim", "evidence_or_data_object", "source_footer"],
                "density": _density(selected),
                "rhythm_position": RHYTHM[index] if index < len(RHYTHM) else "support",
                "source_content_interpretation_goal": _interpretation_goal(selected),
                "avoid": ["reference fixture labels", "internal layout labels", "full-slide reference backgrounds", "semantic raster fallback"],
                "canva_parity_claimed": False,
            }
        )
    failures = []
    if any(row["focal_object"] == "title_text_only" for row in slides):
        failures.append("title_only_focal_object")
    if len({row["rhythm_position"] for row in slides}) < 8:
        failures.append("insufficient_rhythm_diversity")
    return {
        "schema_name": "slide_art_direction_plan",
        "status": "passed" if not failures else "failed",
        "slide_count": len(slides),
        "failures": failures,
        "slides": slides,
        "canva_parity_claimed": False,
    }


def _narrative_role(index: int, selected: str) -> str:
    if index < len(RHYTHM):
        return RHYTHM[index]
    return selected.replace("_", " ")


def _focal_object(reference_id: str) -> str:
    if "dashboard" in reference_id:
        return "dominant native chart with KPI strip"
    if "table" in reference_id or "matrix" in reference_id:
        return "editable matrix/table as main information object"
    if "roadmap" in reference_id:
        return "timeline rail with milestone hierarchy"
    if "process" in reference_id or "framework" in reference_id:
        return "directional workflow or layered framework object"
    if "toc" in reference_id:
        return "navigation route with active marker"
    if "evidence" in reference_id:
        return "claim/evidence/source stack"
    if "cover" in reference_id or "maritime" in reference_id:
        return "hero visual field plus thesis"
    return "source-bound card cluster with evidence markers"


def _density(reference_id: str) -> str:
    if "table" in reference_id or "dashboard" in reference_id:
        return "dense"
    if "cover" in reference_id or "toc" in reference_id:
        return "light"
    return "medium"


def _interpretation_goal(reference_id: str) -> str:
    return f"Use {reference_id} to make the source claim visible as an editable semantic object rather than pasted prose."
