"""Run PDFB02 conversion strategies on real PDF/PPT-like fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.pdfb01_conversion_strategies import STRATEGY_IDS, run_all_strategies_for_fixture


PDFB02_STRATEGY_IDS = list(STRATEGY_IDS)


def run_pdfb02_strategies_for_fixture(fixture: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    result = run_all_strategies_for_fixture(_as_pdfb01_fixture(fixture), output_dir)
    result["schema_name"] = "pdfb02_fixture_strategy_run_report"
    result["fixture_id"] = fixture["fixture_id"]
    for strategy in result["strategy_results"].values():
        strategy["pdfb02_fixture_style_family"] = fixture.get("style_family")
        strategy["pdfb02_background_mode"] = fixture.get("background_mode")
        strategy["uses_pdf_object_truth"] = True
    return result


def _as_pdfb01_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "fixture_id": fixture["fixture_id"],
        "title": fixture["title"],
        "fixture_dir": fixture["fixture_dir"],
        "reference_image": fixture["reference_image"],
        "semantic_slot_count": fixture["semantic_slot_count"],
        "requires_chart": fixture.get("requires_chart", False),
        "requires_table": fixture.get("requires_table", False),
        "canva_parity_claimed": False,
    }
