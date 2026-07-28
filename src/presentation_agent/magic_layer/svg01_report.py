"""Report helpers for SVG01."""

from __future__ import annotations

from typing import Any


def simple_report_markdown(report: dict[str, Any], title: str | None = None) -> str:
    heading = title or report.get("schema_name", "report")
    lines = [f"# {heading}", "", f"- status: `{report.get('status', 'unknown')}`"]
    for key in (
        "decision",
        "svg_asset_count",
        "asset_count",
        "resolution_count",
        "unresolved_required_count",
        "validated_asset_count",
        "embedded_raster_count",
        "external_dependency_count",
        "semantic_icon_count",
        "semantic_icon_with_source_svg_provenance_count",
        "semantic_icon_raster_fallback_count",
        "empty_circle_placeholder_count",
    ):
        if key in report:
            lines.append(f"- {key}: `{report[key]}`")
    if "failures" in report:
        lines.append(f"- failures: `{', '.join(report['failures']) if report['failures'] else 'none'}`")
    lines.append("- canva_parity_claimed: `false`")
    return "\n".join(lines) + "\n"


def final_decision_markdown(final: dict[str, Any]) -> str:
    return (
        "# SVG01 Final Decision\n\n"
        f"- decision: `{final['decision']}`\n"
        f"- status: `{final['status']}`\n"
        f"- E03H-P2 unlocked: `{str(final.get('e03h_p2_unlocked', False)).lower()}`\n"
        f"- E04H unlocked: `{str(final.get('e04h_unlocked', False)).lower()}`\n"
        f"- E05 unlocked: `{str(final.get('e05_unlocked', False)).lower()}`\n"
        "- broad Canva parity claimed: `false`\n"
    )
