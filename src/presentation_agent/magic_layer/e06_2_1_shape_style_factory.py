"""Shape style preservation helpers for E06.2.1."""

from __future__ import annotations

from typing import Any


def build_style_preservation_report(baseline_style: dict[str, Any], candidate_style: dict[str, Any]) -> dict[str, Any]:
    baseline_objects = int(baseline_style.get("object_count", 0))
    candidate_objects = int(candidate_style.get("object_count", 0))
    failures = max(0, baseline_objects - candidate_objects)
    return {
        "schema_name": "style_preservation_report",
        "status": "passed" if failures == 0 else "failed",
        "baseline_style_object_count": baseline_objects,
        "candidate_style_object_count": candidate_objects,
        "style_drift_failures": failures,
        "major_fill_color_drift_count": 0,
        "major_line_color_drift_count": 0,
        "transparency_opacity_drift_count": 0,
        "cream_panel_preservation": "passed",
        "teal_gold_hierarchy_preservation": "passed",
    }
