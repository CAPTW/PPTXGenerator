"""Editorial integrity aggregation for E04-R3."""

from __future__ import annotations

from typing import Any


def build_editorial_integrity_report(
    visible_text_inventory_r2: dict[str, Any],
    leakage_report: dict[str, Any],
    truncation_report: dict[str, Any],
    copy_plan: dict[str, Any],
    component_role_report: dict[str, Any],
) -> dict[str, Any]:
    passed = (
        copy_plan.get("status") == "passed"
        and component_role_report.get("status") == "passed"
        and truncation_report.get("source_text_truncation_count", 0) == 0
    )
    return {
        "schema_name": "e04_r3_editorial_integrity_report",
        "status": "passed" if passed else "failed",
        "r2_visible_text_count": visible_text_inventory_r2.get("visible_text_count", 0),
        "r2_internal_label_leakage_count": leakage_report.get("internal_label_leakage_count", 0),
        "r3_planned_source_text_truncation_count": truncation_report.get("source_text_truncation_count", 0),
        "copy_rewrite_status": copy_plan.get("status"),
        "component_role_consistency_status": component_role_report.get("status"),
        "editorial_cleanup_actions": [
            "remove visible internal art-direction labels",
            "replace diagnostic labels with audience-facing source-safe copy",
            "preserve source and citation refs",
            "keep chart and table copy aligned with native components",
        ],
        "canva_parity_claimed": False,
    }


def editorial_integrity_report_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# E04 R3 Editorial Integrity Report",
            "",
            f"- Status: `{report['status']}`",
            f"- R2 internal label leakage count: `{report['r2_internal_label_leakage_count']}`",
            f"- Planned R3 source text truncation count: `{report['r3_planned_source_text_truncation_count']}`",
            f"- Copy rewrite status: `{report['copy_rewrite_status']}`",
            f"- Component role consistency: `{report['component_role_consistency_status']}`",
            f"- Canva parity claimed: `{report['canva_parity_claimed']}`",
        ]
    )
