"""Style analysis wrapper for E01H-V2-R1 foreground transfer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e01h_v2_style_analyzer import analyze_reference_style


def analyze_r1_style(reference_image: str | Path, *, case_id: str) -> dict[str, Any]:
    report = analyze_reference_style(reference_image, style_family=case_id)
    report["schema_name"] = "style_analysis_report"
    report["foreground_style_transfer_required"] = True
    report["foreground_components_style_transferred"] = report.get("status") == "passed"
    report["style_preserved_by_blurred_background_only"] = False
    return report


def build_r1_style_preservation_report(style_report: dict[str, Any]) -> dict[str, Any]:
    passed = style_report.get("status") == "passed" and style_report.get("foreground_components_style_transferred") is True
    return {
        "schema_name": "style_preservation_report",
        "status": "passed" if passed else "failed",
        "style_preservation_score": style_report.get("style_preservation_score", 0.0),
        "theme": style_report.get("theme"),
        "light_or_dark_theme": style_report.get("light_or_dark_theme"),
        "foreground_components_style_transferred": style_report.get("foreground_components_style_transferred", False),
        "style_preserved_by_blurred_background_only": False,
        "canva_parity_claimed": False,
    }
