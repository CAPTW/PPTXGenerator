"""Source/footer readability gate for E04.2."""

from __future__ import annotations

from typing import Any


def build_e04_2_source_footer_readability_report(text_report: dict[str, Any]) -> dict[str, Any]:
    target_rows = [row for row in text_report.get("rows", []) if row.get("target_slide")]
    target_min = min((row.get("minimum_font_pt") or 99.0 for row in target_rows), default=99.0)
    return {
        "schema_name": "e04_2_source_footer_readability_report",
        "status": "passed" if target_min >= 6.0 else "failed",
        "verdict": "passed" if target_min >= 6.0 else "patch_required",
        "minimum_target_slide_font_pt": target_min,
        "source_footer_readability_policy": "no source/data support text below 6pt; preferred product polish target is 7pt where density allows",
    }

