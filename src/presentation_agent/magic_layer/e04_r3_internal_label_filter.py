"""Detect and filter internal planning labels from visible slide copy."""

from __future__ import annotations

from typing import Any


INTERNAL_LABEL_PATTERNS = [
    "visual field",
    "navigation route",
    "active decision path",
    "evidence stack",
    "artifact system chain",
    "layered four-stage framework stack",
    "gate cadence chain",
    "native comparison matrix",
    "dominant native chart",
    "native governance table",
    "timeline rail",
    "main information object",
    "component",
    "layout",
    "composition",
    "focal object",
    "template",
    "archetype",
]


def is_internal_label(value: str) -> bool:
    text = " ".join(str(value).lower().split())
    return any(pattern in text for pattern in INTERNAL_LABEL_PATTERNS)


def build_internal_label_leakage_report(visible_text_inventory: dict[str, Any]) -> dict[str, Any]:
    leakages = [
        row
        for row in visible_text_inventory.get("rows", [])
        if row.get("is_internal_art_direction_label") or is_internal_label(row.get("visible_text", ""))
    ]
    return {
        "schema_name": "internal_label_leakage_report",
        "status": "passed" if not leakages else "failed",
        "internal_label_leakage_count": len(leakages),
        "leakages": leakages,
        "canva_parity_claimed": False,
    }


def internal_label_leakage_report_markdown(report: dict[str, Any]) -> str:
    lines = ["# Internal Label Leakage Report", "", f"- Status: `{report['status']}`", f"- Leakage count: `{report['internal_label_leakage_count']}`"]
    if report["leakages"]:
        lines.extend(["", "| Slide | Text |", "|---|---|"])
        for row in report["leakages"]:
            lines.append(f"| {row.get('slide_id')} | {row.get('visible_text')} |")
    return "\n".join(lines)
