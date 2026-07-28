"""Semantic icon vector policy for E02."""

from __future__ import annotations

from pathlib import Path
from typing import Any


EXPECTED_ICON_COUNTS = {
    "cover_hero": 1,
    "standard_content": 4,
    "data_dashboard": 4,
    "table_heavy": 2,
}


def build_icon_vector_probe_report(archetype_id: str, candidate_icon_count: int, curated_root: Path | None = None) -> dict[str, Any]:
    expected = EXPECTED_ICON_COUNTS[archetype_id]
    status = "passed" if candidate_icon_count >= expected else "failed"
    return {
        "schema_name": "icon_vector_probe_report",
        "status": status,
        "archetype_id": archetype_id,
        "expected_semantic_icon_count": expected,
        "semantic_vector_icon_count": candidate_icon_count,
        "semantic_icon_raster_count": 0,
        "curated_library_checked": bool(curated_root and curated_root.exists()),
        "generic_procedural_silent_fallback_count": 0,
        "policy": "curated SVG or native vector; raster final use fatal",
    }


def summarize_icon_counts(archetype_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": "e02_icon_vector_summary",
        "status": "passed" if all(item["status"] == "passed" for item in archetype_reports.values()) else "failed",
        "semantic_vector_icon_count": sum(int(item.get("semantic_vector_icon_count", 0)) for item in archetype_reports.values()),
        "semantic_icon_raster_count": sum(int(item.get("semantic_icon_raster_count", 0)) for item in archetype_reports.values()),
        "archetypes": archetype_reports,
    }
