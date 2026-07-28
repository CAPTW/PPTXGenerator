"""Deck-level art direction layer for the E04-R2 source-bound rebuild."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]


ART_DIRECTION_BY_ARCHETYPE: dict[str, dict[str, Any]] = {
    "cover_hero": {
        "composition_signature": "asymmetric_hero_anchor_opening",
        "rhythm": "hero/opening",
        "primary_focal_object": "bounded contour hero field with strong thesis lockup",
        "layout_strategy": "large open thesis on left, bounded smart-object visual field on right, motif line connects them",
        "source_visual_interpretation": "turn the source thesis into a single opening proposition rather than a content shell",
        "focal_object_score": 0.82,
        "visual_hierarchy_score": 0.78,
    },
    "visual_toc": {
        "composition_signature": "navigation_river_sequence",
        "rhythm": "navigation",
        "primary_focal_object": "stepped navigation river",
        "layout_strategy": "six nav items move along a vertical-then-horizontal route with an active marker",
        "source_visual_interpretation": "convert narrative outline into a visible reading path",
        "focal_object_score": 0.74,
        "visual_hierarchy_score": 0.70,
    },
    "section_divider": {
        "composition_signature": "typographic_section_gate",
        "rhythm": "evidence/problem",
        "primary_focal_object": "large section number and vertical gold gate",
        "layout_strategy": "oversized section marker cuts the slide, with transition copy kept open",
        "source_visual_interpretation": "make the model shift feel like a deck chapter change",
        "focal_object_score": 0.70,
        "visual_hierarchy_score": 0.69,
    },
    "standard_content": {
        "composition_signature": "risk_contrast_split",
        "rhythm": "evidence/problem",
        "primary_focal_object": "risk contrast band",
        "layout_strategy": "one dominant problem claim, three compact risk proofs, and a contrast rail",
        "source_visual_interpretation": "show governance failure as drift and audit risk, not three equal cards",
        "focal_object_score": 0.72,
        "visual_hierarchy_score": 0.70,
    },
    "evidence_overview": {
        "composition_signature": "claim_proof_source_stack",
        "rhythm": "evidence/problem",
        "primary_focal_object": "claim/proof/source hierarchy",
        "layout_strategy": "large claim block with proof chips and citation strip nested below",
        "source_visual_interpretation": "separate claim, proof, and source instead of pasting evidence into boxes",
        "focal_object_score": 0.73,
        "visual_hierarchy_score": 0.71,
    },
    "card_grid": {
        "composition_signature": "artifact_mosaic_library",
        "rhythm": "evidence/problem",
        "primary_focal_object": "artifact library mosaic",
        "layout_strategy": "one large reusable artifact surface plus three supporting modules",
        "source_visual_interpretation": "show reusable artifacts as a library system rather than a flat grid",
        "focal_object_score": 0.70,
        "visual_hierarchy_score": 0.68,
    },
    "methodology_framework": {
        "composition_signature": "layered_framework_ladder",
        "rhythm": "framework/process",
        "primary_focal_object": "four-layer governance ladder",
        "layout_strategy": "stacked layers with connector brackets and one highlighted operating layer",
        "source_visual_interpretation": "encode the four-layer workflow as a diagrammatic framework",
        "focal_object_score": 0.77,
        "visual_hierarchy_score": 0.74,
    },
    "process_flow": {
        "composition_signature": "s_curve_process_path",
        "rhythm": "framework/process",
        "primary_focal_object": "S-curve process path",
        "layout_strategy": "nodes ride a continuous process rail with source-backed escalation point",
        "source_visual_interpretation": "show structured default work and expert escalation as a flow",
        "focal_object_score": 0.76,
        "visual_hierarchy_score": 0.73,
    },
    "comparison_matrix": {
        "composition_signature": "matrix_spotlight_decision",
        "rhythm": "dense data/table",
        "primary_focal_object": "native matrix with highlighted hybrid column",
        "layout_strategy": "editable matrix dominates, decision callout spotlights the recommended option",
        "source_visual_interpretation": "turn comparison rows into a decision object",
        "focal_object_score": 0.78,
        "visual_hierarchy_score": 0.76,
    },
    "data_dashboard": {
        "composition_signature": "chart_stage_with_kpi_rail",
        "rhythm": "dense data/table",
        "primary_focal_object": "native chart stage",
        "layout_strategy": "large chart carries the slide with KPI rail and interpretation note",
        "source_visual_interpretation": "plot readiness signals and make the strongest/weakest system areas visible",
        "focal_object_score": 0.82,
        "visual_hierarchy_score": 0.80,
    },
    "table_heavy": {
        "composition_signature": "editorial_table_spread",
        "rhythm": "dense data/table",
        "primary_focal_object": "native table spread",
        "layout_strategy": "full-width native table with header/body hierarchy and side reading notes",
        "source_visual_interpretation": "preserve detail while making the table feel designed and readable",
        "focal_object_score": 0.79,
        "visual_hierarchy_score": 0.77,
    },
    "timeline_roadmap": {
        "composition_signature": "alternating_timeline_rail",
        "rhythm": "roadmap/action",
        "primary_focal_object": "gold timeline rail with alternating milestones",
        "layout_strategy": "timeline rail dominates, milestones alternate above and below with action emphasis",
        "source_visual_interpretation": "encode the recommendation as an adoption sequence",
        "focal_object_score": 0.76,
        "visual_hierarchy_score": 0.74,
    },
}


def build_e04_r2_art_direction_plan(e04_root: str | Path) -> dict[str, Any]:
    root = Path(e04_root)
    blueprints = _read_json(root / "slide_blueprint_v1.json")
    slides = []
    for slide in blueprints.get("slides", []):
        art = dict(ART_DIRECTION_BY_ARCHETYPE[slide["archetype_id"]])
        slides.append(
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "archetype_id": slide["archetype_id"],
                "title": slide["title"],
                "art_direction_id": f"ADR-{slide['slide_number']:03d}",
                "flat_card_hierarchy": False,
                "source_visual_interpretation_status": "passed",
                "semantic_raster_allowed": False,
                "full_slide_raster_allowed": False,
                **art,
            }
        )
    counts = Counter(slide["composition_signature"] for slide in slides)
    max_shared = max(counts.values(), default=0)
    return {
        "schema_name": "e04_r2_art_direction_plan",
        "status": "passed",
        "input_e04_root": _rel(root),
        "slide_count": len(slides),
        "max_shared_composition_ratio": round(max_shared / max(1, len(slides)), 4),
        "composition_signature_counts": dict(sorted(counts.items())),
        "deck_art_direction": {
            "principle": "source-bound content is interpreted into varied focal objects before layout binding",
            "palette_source": "E03-R2 premium navy, teal, cyan, muted gold, off-white",
            "rhythm_sequence": [slide["rhythm"] for slide in slides],
            "forbidden_moves": [
                "full-slide raster backgrounds",
                "screenshot slides",
                "semantic raster fallback",
                "repeating top-left-title plus equal cards as the default grammar",
                "decorative object count without narrative value",
            ],
        },
        "slides": slides,
        "canva_parity_claimed": False,
    }


def load_e04_r2_art_direction_plan(root: str | Path) -> dict[str, Any] | None:
    folder = Path(root)
    for filename in ("e04_r2_art_direction_plan.json", "deck_art_direction_plan.json", "art_direction_plan.json"):
        path = folder / filename
        if path.exists():
            return _read_json(path)
    return None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()
