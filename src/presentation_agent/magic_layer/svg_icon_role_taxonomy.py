"""Semantic SVG icon role taxonomy for Magic Layer D03."""

from __future__ import annotations

from typing import Any


ROLE_SPECS: dict[str, dict[str, Any]] = {
    "document": {"preferred": ["tabler__book", "book"], "fallback": ["file-text", "notes"], "contexts": ["standard_content", "case_study", "source_footer"]},
    "file_text": {"preferred": ["file-text", "tabler__book"], "fallback": ["book", "article"], "contexts": ["source_footer", "evidence"]},
    "checklist": {"preferred": ["list-check", "tabler__list-numbers"], "fallback": ["checks", "clipboard-check"], "contexts": ["process", "decision"]},
    "database": {"preferred": ["tabler__database", "database"], "fallback": ["server", "binary-tree"], "contexts": ["dashboard", "evidence", "table"]},
    "chart_bar": {"preferred": ["chart-bar", "tabler__chart-donut"], "fallback": ["chart-histogram", "chart-dots"], "contexts": ["dashboard", "chart"]},
    "chart_line": {"preferred": ["chart-line", "chart-arrows-vertical"], "fallback": ["trending-up", "tabler__chart-donut"], "contexts": ["dashboard", "timeline"]},
    "pie_chart": {"preferred": ["chart-pie", "tabler__chart-donut"], "fallback": ["chart-donut"], "contexts": ["dashboard", "chart"]},
    "shield": {"preferred": ["tabler__shield-check", "shield-check"], "fallback": ["shield", "lock"], "contexts": ["governance", "risk"]},
    "check": {"preferred": ["tabler__circle-check", "circle-check"], "fallback": ["checks", "check"], "contexts": ["decision", "evidence"]},
    "alert": {"preferred": ["tabler__alert-circle", "alert-circle"], "fallback": ["alert-triangle"], "contexts": ["risk", "warning"]},
    "warning": {"preferred": ["tabler__alert-triangle", "alert-triangle"], "fallback": ["alert-circle"], "contexts": ["risk", "warning"]},
    "lock": {"preferred": ["lock", "lock-check"], "fallback": ["shield-lock", "tabler__shield-check"], "contexts": ["governance", "security"]},
    "users": {"preferred": ["users", "users-group"], "fallback": ["tabler__user", "user"], "contexts": ["owner", "audience"]},
    "user": {"preferred": ["tabler__user", "user"], "fallback": ["tabler__user-scan", "user-circle"], "contexts": ["owner", "presenter"]},
    "calendar": {"preferred": ["tabler__calendar", "calendar"], "fallback": ["calendar-time", "calendar-event"], "contexts": ["timeline", "footer"]},
    "clock": {"preferred": ["clock", "clock-hour-4"], "fallback": ["calendar-time", "tabler__calendar"], "contexts": ["timeline", "process"]},
    "target": {"preferred": ["target", "target-arrow"], "fallback": ["tabler__gauge", "focus"], "contexts": ["kpi", "goal"]},
    "route": {"preferred": ["tabler__route", "route"], "fallback": ["timeline", "arrows-split"], "contexts": ["process", "workflow"]},
    "link": {"preferred": ["link", "tabler__route"], "fallback": ["external-link", "unlink"], "contexts": ["source", "citation"]},
    "network": {"preferred": ["network", "nodes"], "fallback": ["sitemap", "git-branch"], "contexts": ["framework", "concept"]},
    "workflow": {"preferred": ["workflow", "tabler__route"], "fallback": ["arrows-split", "git-branch"], "contexts": ["process", "methodology"]},
    "brain": {"preferred": ["brain", "bulb"], "fallback": ["tabler__bulb", "sparkles"], "contexts": ["insight", "ai"]},
    "scale": {"preferred": ["scale", "balance"], "fallback": ["shield-check", "tabler__shield-check"], "contexts": ["governance", "decision"]},
    "decision": {"preferred": ["tabler__circle-check", "circle-check"], "fallback": ["message-check", "checkbox"], "contexts": ["decision", "recommendation"]},
    "evidence": {"preferred": ["tabler__message-check", "message-check"], "fallback": ["microscope", "tabler__microscope"], "contexts": ["evidence", "source"]},
    "source": {"preferred": ["tabler__world", "world"], "fallback": ["tabler__book", "book"], "contexts": ["source_footer", "citation"]},
    "citation": {"preferred": ["tabler__quote", "quote"], "fallback": ["blockquote", "book"], "contexts": ["source_footer", "citation"]},
    "search": {"preferred": ["search", "zoom"], "fallback": ["zoom-check", "world-search"], "contexts": ["evidence", "audit"]},
    "settings": {"preferred": ["settings", "tabler__tools"], "fallback": ["adjustments", "tools"], "contexts": ["methodology", "control"]},
    "flag": {"preferred": ["flag", "pennant"], "fallback": ["bookmark", "tabler__bookmark"], "contexts": ["milestone", "section"]},
    "star": {"preferred": ["star", "sparkles"], "fallback": ["tabler__bulb", "award"], "contexts": ["highlight", "insight"]},
    "trophy": {"preferred": ["tabler__trophy", "trophy"], "fallback": ["award", "star"], "contexts": ["success", "closing"]},
    "archive": {"preferred": ["tabler__archive", "archive"], "fallback": ["folder", "box"], "contexts": ["memory", "appendix"]},
    "folder": {"preferred": ["folder", "folders"], "fallback": ["tabler__archive", "archive"], "contexts": ["source", "appendix"]},
    "book": {"preferred": ["tabler__book", "book"], "fallback": ["school", "tabler__school"], "contexts": ["source", "academic"]},
    "globe": {"preferred": ["tabler__world", "world"], "fallback": ["world-www", "map"], "contexts": ["source", "global"]},
    "anchor": {"preferred": ["anchor", "bookmark"], "fallback": ["tabler__bookmark", "flag"], "contexts": ["section", "navigation"]},
    "generic_icon": {"preferred": ["tabler__tools", "tools"], "fallback": ["circle", "square"], "contexts": ["unknown", "decorative"]},
}


def build_svg_icon_role_taxonomy() -> dict[str, Any]:
    roles = []
    for role, spec in ROLE_SPECS.items():
        roles.append(
            {
                "role": role,
                "preferred_svg_names": spec["preferred"],
                "fallback_svg_names": spec["fallback"],
                "semantic_meaning": _meaning(role),
                "allowed_archetype_contexts": spec["contexts"],
                "final_editability_target": "svg_vector",
                "raster_fallback_policy": "forbidden_for_semantic_icon",
                "decorative_exception_policy": "allowed_only_when_nonsemantic_and_recorded",
            }
        )
    return {
        "schema_name": "svg_icon_role_taxonomy_v1",
        "status": "passed",
        "roles": roles,
        "role_count": len(roles),
        "ocr_dependency": "none; OCR unavailable risk is carried forward",
    }


def taxonomy_by_role(taxonomy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {role["role"]: role for role in taxonomy.get("roles") or []}


def _meaning(role: str) -> str:
    return f"Semantic marker for {role.replace('_', ' ')} contexts; it supports editable content and never replaces text, chart, or table data."

