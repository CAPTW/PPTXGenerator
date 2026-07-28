"""Adapt PDF/PPT-like extraction signals into E01H-V2 hints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.pdfb02_object_extraction import extract_pdfb02_object_signals


def adapt_pdf_signals(fixture_dir: str | Path) -> dict[str, Any]:
    folder = Path(fixture_dir)
    if not (folder / "reference.pdf").exists():
        return {
            "schema_name": "pdf_object_signal_report",
            "status": "not_available",
            "fixture_id": folder.name,
            "reference_pdf_available": False,
            "hints": {"text_zone_hint_count": 0, "vector_zone_hint_count": 0, "image_backplate_hint_count": 0},
            "canva_parity_claimed": False,
        }
    report = extract_pdfb02_object_signals(folder)
    report = dict(report)
    report["schema_name"] = "pdf_object_signal_report"
    report["reference_pdf_available"] = True
    report["hints"] = {
        "text_zone_hint_count": report.get("text_span_count", 0),
        "vector_zone_hint_count": report.get("vector_shape_count", 0),
        "image_backplate_hint_count": report.get("image_object_count", 0),
        "table_grid_hint_score": report.get("signal_value", {}).get("table_grid_detection", 0.0),
        "chart_region_hint_score": report.get("signal_value", {}).get("chart_region_detection", 0.0),
    }
    return report
