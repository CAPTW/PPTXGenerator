"""Deterministic E04 presentation planner."""

from __future__ import annotations

from typing import Any


E04_ARCHETYPE_SEQUENCE = [
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
]


def build_presentation_plan(source_document_graph: dict[str, Any]) -> dict[str, Any]:
    title = source_document_graph.get("title") or "Source-Bound Governance Deck"
    return {
        "schema_name": "presentation_plan_v1",
        "status": "passed",
        "plan_id": "E04-PLAN-001",
        "source_document_id": source_document_graph.get("document_id"),
        "source_bound": True,
        "fixture_mode": False,
        "title": title,
        "audience": "AI governance product, risk, legal, and research stakeholders",
        "objective": "Convert a local source document into an editable 12-slide evidence-centered sample deck.",
        "slide_count_target": 12,
        "archetypes": list(E04_ARCHETYPE_SEQUENCE),
        "narrative_arc": [
            "establish the governance problem",
            "show the source-backed operating model",
            "compare choices with evidence",
            "bind metrics and tables into native PPT components",
            "close with an adoption roadmap",
        ],
        "sections": [
            {"section_id": "sec-01", "title": "Context and framing", "slide_range": [1, 4]},
            {"section_id": "sec-02", "title": "Evidence and operating model", "slide_range": [5, 8]},
            {"section_id": "sec-03", "title": "Decision support", "slide_range": [9, 12]},
        ],
        "citation_footer_required": True,
        "native_chart_required": True,
        "native_table_required": True,
        "canva_parity_claimed": False,
    }


def build_narrative_outline(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "narrative_outline_v1",
        "status": "passed",
        "plan_id": plan["plan_id"],
        "title": plan["title"],
        "outline": [
            {"order": 1, "label": "Why governance needs evidence anchors", "slide_ids": ["SLIDE-001", "SLIDE-002", "SLIDE-003", "SLIDE-004"]},
            {"order": 2, "label": "How the operating model works", "slide_ids": ["SLIDE-005", "SLIDE-006", "SLIDE-007", "SLIDE-008"]},
            {"order": 3, "label": "What decision support proves", "slide_ids": ["SLIDE-009", "SLIDE-010", "SLIDE-011", "SLIDE-012"]},
        ],
        "canva_parity_claimed": False,
    }


def build_slide_type_distribution(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "slide_type_distribution_report",
        "status": "passed",
        "slide_count": plan["slide_count_target"],
        "archetype_counts": {archetype_id: 1 for archetype_id in plan["archetypes"]},
        "native_chart_slide_count": 1,
        "native_table_slide_count": 2,
        "source_bound": True,
        "canva_parity_claimed": False,
    }
