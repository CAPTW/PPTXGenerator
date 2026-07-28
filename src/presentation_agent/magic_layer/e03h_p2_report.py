"""Markdown helpers for E03H-P2 reports."""

from __future__ import annotations

from typing import Any


def simple_report_markdown(report: dict[str, Any], title: str | None = None) -> str:
    title = title or report.get("schema_name", "Report")
    lines = [f"# {title}", "", f"- status: `{report.get('status', 'unknown')}`"]
    for key in (
        "decision",
        "required_semantic_icon_count",
        "required_semantic_icon_svg_bound_coverage",
        "semantic_icon_raster_fallback_count",
        "empty_circle_placeholder_count",
        "procedural_native_glyph_without_source_svg_asset_id_count",
        "semantic_raster_violation_count",
        "unknown_content_bearing_layer_count",
        "e04h_unlocked",
        "e05_unlocked",
    ):
        if key in report:
            lines.append(f"- {key}: `{report[key]}`")
    lines.append("- canva_parity_claimed: `false`")
    return "\n".join(lines) + "\n"


def final_decision_markdown(final: dict[str, Any]) -> str:
    return simple_report_markdown(final, "E03H-P2 Final Decision")
