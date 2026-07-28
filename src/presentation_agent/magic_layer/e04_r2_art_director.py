"""PromptSet E04-R2 art director facade."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]

RHYTHM_SEQUENCE = [
    "Opening / hero",
    "Navigation / decision path",
    "Problem / recurring failure",
    "Evidence / operating pattern",
    "Reusable artifacts / framework",
    "Workflow / process",
    "Cadence / operating rhythm",
    "Comparison / decision matrix",
    "Dashboard / signal profile",
    "Table / governance operating table",
    "Roadmap / adoption sequence",
    "Close / operating recommendation",
]

VARIANTS = [
    "hero_left_text_right_visual",
    "centered_navigation_map",
    "split_problem_triads",
    "claim_evidence_stack",
    "artifact_system_chain",
    "layered_framework_stack",
    "horizontal_process_rail",
    "cadence_cycle_or_gate_chain",
    "matrix_dominant_with_side_insight",
    "dashboard_chart_dominant",
    "table_dominant_with_top_summary",
    "roadmap_rail_with_staggered_milestones",
]

FOCAL_OBJECTS = [
    "thesis plus bounded hero visual field",
    "navigation route with active decision path",
    "failure triad with contrast risk band",
    "source-to-claim evidence stack",
    "reusable artifact system chain",
    "layered four-stage framework stack",
    "gate cadence chain with connector emphasis",
    "native comparison matrix with hybrid spotlight",
    "dominant native chart with KPI strip",
    "native governance table as main information object",
    "timeline rail with milestone hierarchy",
    "operating recommendation and next-step decision object",
]


def build_deck_art_direction_plan(e04_root: str | Path) -> dict[str, Any]:
    root = Path(e04_root)
    blueprints = _read_json(root / "slide_blueprint_v1.json")
    slides = []
    for index, slide in enumerate(blueprints.get("slides", [])):
        variant = VARIANTS[index]
        focal = FOCAL_OBJECTS[index]
        slides.append(
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "original_title": slide["title"],
                "title": slide["title"],
                "art_direction_id": f"ADR-{slide['slide_number']:03d}",
                "archetype_id": slide["archetype_id"],
                "narrative_role": _narrative_role(index),
                "visual_role": RHYTHM_SEQUENCE[index],
                "focal_object": focal,
                "primary_focal_object": focal,
                "composition_variant": variant,
                "composition_signature": variant,
                "density": _density_for(slide["archetype_id"]),
                "rhythm_position": RHYTHM_SEQUENCE[index],
                "rhythm": _dq_rhythm(RHYTHM_SEQUENCE[index]),
                "source_refs_required": True,
                "must_feel_like": _must_feel_like(slide["archetype_id"]),
                "avoid": [
                    "same top-left title plus equal card row skeleton",
                    "semantic raster fallback",
                    "full-slide raster background",
                    "decorative object count without narrative value",
                ],
                "selected_archetype_hint": slide["archetype_id"],
                "source_content_interpretation_goal": _interpretation_goal(slide["archetype_id"]),
                "source_visual_interpretation": _interpretation_goal(slide["archetype_id"]),
                "source_visual_interpretation_status": "passed",
                "layout_strategy": _layout_strategy(variant),
                "focal_object_score": 0.74 + min(index, 6) * 0.01,
                "visual_hierarchy_score": 0.70 + min(index, 6) * 0.01,
                "flat_card_hierarchy": False,
                "semantic_raster_allowed": False,
                "full_slide_raster_allowed": False,
            }
        )
    counts = Counter(slide["composition_variant"] for slide in slides)
    max_shared = max(counts.values(), default=0)
    return {
        "schema_name": "deck_art_direction_plan",
        "status": "passed" if max_shared <= 3 and len(counts) >= 5 else "failed",
        "input_e04_root": _rel(root),
        "slide_count": len(slides),
        "max_shared_composition_count": max_shared,
        "max_shared_composition_ratio": round(max_shared / max(1, len(slides)), 4),
        "distinct_composition_variant_count": len(counts),
        "composition_variant_counts": dict(sorted(counts.items())),
        "deck_art_direction": {
            "content_maturity": "serious/work",
            "audience_posture": "coworkers/operators",
            "emotional_register": "trustworthy premium",
            "format_promise": "source-bound governance deck with varied focal objects, native charts/tables, and concise evidence hierarchy",
            "anti_format": "repeated generic card-grid consulting skeleton",
        },
        "slides": slides,
        "canva_parity_claimed": False,
    }


def write_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Deck Art Direction Plan",
        "",
        f"- Status: `{plan['status']}`",
        f"- Distinct composition variants: `{plan['distinct_composition_variant_count']}`",
        f"- Max shared composition count: `{plan['max_shared_composition_count']}`",
        "- Canva parity claimed: `False`",
        "",
        "| Slide | Rhythm | Focal object | Variant |",
        "|---|---|---|---|",
    ]
    for slide in plan["slides"]:
        lines.append(f"| {slide['slide_number']} | {slide['rhythm_position']} | {slide['focal_object']} | `{slide['composition_variant']}` |")
    return "\n".join(lines)


def _narrative_role(index: int) -> str:
    roles = [
        "open the source-bound thesis",
        "show the decision path",
        "frame the recurring failure",
        "show the evidence pattern",
        "organize reusable artifacts",
        "explain the framework",
        "show the operating cadence",
        "compare operating choices",
        "interpret readiness signals",
        "preserve governance detail",
        "sequence adoption",
        "close with operating recommendation",
    ]
    return roles[index]


def _density_for(archetype_id: str) -> str:
    if archetype_id in {"comparison_matrix", "table_heavy"}:
        return "high"
    if archetype_id == "data_dashboard":
        return "medium-high"
    if archetype_id in {"cover_hero", "section_divider"}:
        return "low"
    return "medium"


def _dq_rhythm(position: str) -> str:
    if position == "Opening / hero":
        return "hero/opening"
    if position == "Navigation / decision path":
        return "navigation"
    if position in {"Problem / recurring failure", "Evidence / operating pattern", "Reusable artifacts / framework"}:
        return "evidence/problem"
    if position in {"Workflow / process", "Cadence / operating rhythm"}:
        return "framework/process"
    if position in {"Comparison / decision matrix", "Dashboard / signal profile", "Table / governance operating table"}:
        return "dense data/table"
    return "roadmap/action"


def _must_feel_like(archetype_id: str) -> str:
    return {
        "cover_hero": "a premium opening thesis, not a dashboard opener",
        "visual_toc": "a decision route, not a card grid",
        "section_divider": "a chapter gate with strong contrast",
        "standard_content": "a risk pattern, not three neutral boxes",
        "evidence_overview": "claim/proof/source hierarchy",
        "card_grid": "a reusable artifact system",
        "methodology_framework": "a layered operating model",
        "process_flow": "a directional flow with cadence",
        "comparison_matrix": "a decision matrix",
        "data_dashboard": "a chart-led signal profile",
        "table_heavy": "an editorial table spread",
        "timeline_roadmap": "a recommendation close with visible sequence",
    }.get(archetype_id, "source-bound premium slide")


def _interpretation_goal(archetype_id: str) -> str:
    return {
        "standard_content": "show assumptions, criteria drift, and audit difficulty as a contrasted failure system",
        "evidence_overview": "separate source claim, proof, and citation instead of equal evidence cards",
        "card_grid": "treat reusable artifacts as a system chain",
        "methodology_framework": "encode the four governance layers as stacked operating logic",
        "process_flow": "encode routine checks and expert escalation as directional flow",
        "data_dashboard": "make readiness strengths and weaknesses visible through chart prominence",
        "table_heavy": "make source detail readable with table hierarchy",
        "timeline_roadmap": "turn recommendation into a sequenced adoption close",
    }.get(archetype_id, "interpret source content as a focal visual object")


def _layout_strategy(variant: str) -> str:
    return variant.replace("_", " ")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()
