"""Deck planning helpers for E04 source-bound small deck."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any


E04_SLIDE_ORDER = (
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
)


def load_c08_source_module() -> Any:
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "scripts" / "run_harness_v3_source_bound_small_deck.py"
    spec = importlib.util.spec_from_file_location("_e04_c08_source_bound_module", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_e04_slide_bindings() -> list[dict[str, Any]]:
    c08 = load_c08_source_module()
    by_archetype = {row["archetype_id"]: row for row in c08.SLIDE_BINDINGS}
    rows: list[dict[str, Any]] = []
    for idx, archetype in enumerate(E04_SLIDE_ORDER, start=1):
        row = copy.deepcopy(by_archetype[archetype])
        row["slide_number"] = idx
        row["slide_id"] = f"e04-{idx:03d}"
        row["source_packet_origin_slide_id"] = by_archetype[archetype]["slide_id"]
        row["citation_ids"] = list(row.get("citation_ids", []))
        row["texts"] = list(row.get("texts", []))
        rows.append(row)
    return rows


def build_e04_deck_plan(source_inventory: dict[str, Any]) -> dict[str, Any]:
    slides = []
    for row in load_e04_slide_bindings():
        slides.append(
            {
                "slide_number": row["slide_number"],
                "slide_id": row["slide_id"],
                "archetype_id": row["archetype_id"],
                "purpose": row["purpose"],
                "source_blueprint_slide_id": row.get("source_blueprint_slide_id"),
                "citation_ids": row.get("citation_ids", []),
                "source_bound": True,
                "template_source": "E03.5 Magic Layer+ icon v7.1 pack",
            }
        )
    return {
        "schema_name": "e04_deck_plan",
        "status": "passed" if source_inventory.get("status") == "passed" and len(slides) == 16 else "blocked",
        "deck_title": "Evidence-Centered AI Governance At Scale",
        "slide_count": len(slides),
        "slide_order_changed": False,
        "slide_order_reasoning": "Uses the E04 requested 16-archetype order.",
        "slides": slides,
        "source_packet_type": source_inventory.get("source_packet_type"),
        "broad_canva_parity_claimed": False,
    }


def build_slide_archetype_assignment(plan: dict[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "slide_number": slide["slide_number"],
            "slide_id": slide["slide_id"],
            "archetype_id": slide["archetype_id"],
            "template_source": slide["template_source"],
        }
        for slide in plan.get("slides", [])
    ]
    return {
        "schema_name": "e04_slide_archetype_assignment",
        "status": "passed" if len(rows) == 16 else "failed",
        "assignment_count": len(rows),
        "assignments": rows,
    }
