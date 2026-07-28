"""Component-role consistency checks for E04-R3 audience copy."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e04_r3_internal_label_filter import is_internal_label


EXPECTED_COMPONENT_ROLES = {
    "cover_hero": "opening/hero",
    "visual_toc": "navigation/decision path",
    "section_divider": "section transition",
    "standard_content": "problem/risk pattern",
    "evidence_overview": "evidence/claim proof",
    "card_grid": "reusable artifacts",
    "methodology_framework": "workflow/process/layered system",
    "process_flow": "workflow/process/layered system",
    "comparison_matrix": "comparison/matrix",
    "data_dashboard": "dashboard/chart/KPI",
    "table_heavy": "table/governance table",
    "timeline_roadmap": "roadmap/timeline",
}


ROLE_KEYWORDS = {
    "comparison_matrix": ("comparison", "tradeoff", "matrix"),
    "data_dashboard": ("dashboard", "signal", "kpi", "chart"),
    "table_heavy": ("table", "governance", "source details"),
    "timeline_roadmap": ("roadmap", "adoption", "sequence"),
    "standard_content": ("failure", "risk", "disconnect", "audit"),
    "process_flow": ("cadence", "checks", "workflow", "review"),
    "methodology_framework": ("workflow", "layer", "capture", "synthesis"),
}


def build_component_role_consistency_report(copy_plan: dict[str, Any]) -> dict[str, Any]:
    """Validate that visible copy reads as the intended component, not as diagnostics."""

    rows = []
    inconsistent = []
    for slide in copy_plan.get("slides", []):
        archetype = slide["archetype_id"]
        expected = EXPECTED_COMPONENT_ROLES.get(archetype, "source-bound content")
        visible_copy = slide.get("visible_copy", {})
        text_values = _flatten_visible_copy(visible_copy)
        combined = " ".join(text_values).lower()
        has_internal_label = any(is_internal_label(value) for value in text_values)
        keyword_set = ROLE_KEYWORDS.get(archetype)
        keyword_match = True if keyword_set is None else any(keyword in combined for keyword in keyword_set)
        status = "passed" if not has_internal_label and keyword_match else "failed"
        row = {
            "slide_id": slide["slide_id"],
            "slide_number": slide["slide_number"],
            "archetype_id": archetype,
            "expected_component_role": expected,
            "visible_title": visible_copy.get("title", ""),
            "status": status,
            "finding": "copy matches component role" if status == "passed" else "copy conflicts with component role or leaks internal label",
        }
        rows.append(row)
        if status != "passed":
            inconsistent.append(row)
    return {
        "schema_name": "component_role_consistency_report",
        "status": "passed" if not inconsistent else "failed",
        "slide_count": len(rows),
        "inconsistent_count": len(inconsistent),
        "inconsistent_component_role_count": len(inconsistent),
        "inconsistent_rows": inconsistent,
        "rows": rows,
        "slides": rows,
        "canva_parity_claimed": False,
    }


def component_role_consistency_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Component Role Consistency Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Inconsistent count: `{report['inconsistent_count']}`",
        "",
        "| Slide | Archetype | Expected role | Status |",
        "|---|---|---|---|",
    ]
    for row in report["rows"]:
        lines.append(f"| {row['slide_number']} | `{row['archetype_id']}` | {row['expected_component_role']} | `{row['status']}` |")
    return "\n".join(lines)


def _flatten_visible_copy(visible_copy: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for value in visible_copy.values():
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        else:
            values.append(str(value))
    return values
