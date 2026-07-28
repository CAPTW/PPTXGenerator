"""Report helpers for E03H-P."""

from __future__ import annotations

from typing import Any


def simple_report_markdown(title: str, report: dict[str, Any]) -> str:
    lines = [f"# {title}", "", f"- Status: `{report.get('status', 'n/a')}`"]
    for key in ("decision", "reason", "reference_count", "weak_reference_count", "semantic_raster_violation_count", "unknown_content_bearing_layer_count", "e04h_unlocked", "e05_unlocked", "canva_parity_claimed"):
        if key in report:
            lines.append(f"- {key}: `{report[key]}`")
    if "weak_reference_ids" in report:
        lines.append(f"- Weak references: `{report['weak_reference_ids']}`")
    return "\n".join(lines)


def final_decision_markdown(report: dict[str, Any]) -> str:
    return simple_report_markdown("E03H-P Final Decision", report)
