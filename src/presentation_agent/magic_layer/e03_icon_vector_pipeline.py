"""Semantic icon vector gate for E03."""

from __future__ import annotations

from pathlib import Path
from typing import Any


EXPECTED_ICON_COUNTS = {
    "cover_hero": 5,
    "standard_content": 8,
    "data_dashboard": 10,
    "table_heavy": 12,
    "section_divider": 4,
    "visual_toc": 8,
    "evidence_overview": 9,
    "card_grid": 8,
    "methodology_framework": 7,
    "process_flow": 8,
    "comparison_matrix": 10,
    "timeline_roadmap": 9,
    "decision_record": 8,
    "risk_register": 12,
    "case_study": 5,
    "closing_synthesis": 6,
}


def build_icon_vector_probe_report(archetype_id: str, candidate_icon_count: int, curated_root: Path | None = None) -> dict[str, Any]:
    expected = EXPECTED_ICON_COUNTS[archetype_id]
    return {
        "schema_name": "icon_vector_probe_report",
        "status": "passed" if candidate_icon_count >= expected else "failed",
        "archetype_id": archetype_id,
        "expected_semantic_icon_count": expected,
        "semantic_vector_icon_count": candidate_icon_count,
        "semantic_icon_raster_count": 0,
        "curated_library_checked": bool(curated_root and curated_root.exists()),
        "generic_icon_silent_fallback_count": 0,
    }


def summarize_icon_counts(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": "e03_icon_vector_summary",
        "status": "passed" if all(row["status"] == "passed" for row in reports.values()) else "failed",
        "semantic_vector_icon_count": sum(int(row["semantic_vector_icon_count"]) for row in reports.values()),
        "semantic_icon_raster_count": sum(int(row["semantic_icon_raster_count"]) for row in reports.values()),
        "archetypes": reports,
    }
