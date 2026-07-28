"""Observed semantic icon inventory for E03.2.1 across the 16 references."""

from __future__ import annotations

from pathlib import Path
from typing import Any


CORE_ARCHETYPES = ("cover_hero", "standard_content", "data_dashboard", "table_heavy")
EXPANSION_ARCHETYPES = (
    "section_divider",
    "visual_toc",
    "evidence_overview",
    "card_grid",
    "methodology_framework",
    "process_flow",
    "comparison_matrix",
    "timeline_roadmap",
    "decision_record",
    "risk_register",
    "case_study",
    "closing_synthesis",
)
ARCHETYPES = (*CORE_ARCHETYPES, *EXPANSION_ARCHETYPES)


P0_ROLES = {
    "document",
    "checklist",
    "database",
    "shield",
    "warning",
    "lock",
    "user",
    "users",
    "chart_bar",
    "table",
    "calendar",
    "clock",
    "flag",
    "decision_diamond",
    "process_node",
    "source",
    "citation",
    "note",
    "risk_status",
    "evidence_trace",
    "kpi",
    "section_marker",
    "milestone_flag",
    "recommendation",
    "next_action",
}


def reference_path_for(archetype_id: str, run_root: Path) -> Path:
    if archetype_id in CORE_ARCHETYPES:
        return run_root / "refs/harness_v3_4core" / f"{archetype_id}.png"
    return run_root / "refs/harness_v3_12_16" / f"{archetype_id}.png"


def build_observed_icon_inventory(run_root: Path) -> dict[str, Any]:
    icons: list[dict[str, Any]] = []
    for archetype in ARCHETYPES:
        reference = reference_path_for(archetype, run_root)
        for idx, spec in enumerate(_specs_for(archetype), start=1):
            role = spec["likely_role"]
            priority = spec.get("priority") or ("P0_REQUIRED_SEMANTIC" if role in P0_ROLES else "P1_HIGH_REUSE")
            icon_id = f"{archetype}_{idx:02d}_{role}"
            icons.append(
                {
                    "archetype_id": archetype,
                    "icon_id": icon_id,
                    "reference_path": reference.as_posix(),
                    "bbox_norm": spec["bbox_norm"],
                    "bbox_px": None,
                    "crop_path": None,
                    "normalized_crop_path": None,
                    "likely_role": role,
                    "component_context": spec["component_context"],
                    "container_type": spec.get("container_type", "icon_well"),
                    "glyph_only_confidence": spec.get("glyph_only_confidence", 0.82),
                    "semantic_or_decorative": "semantic",
                    "required_for_template_conversion": priority.startswith(("P0", "P1")),
                    "priority": priority,
                }
            )
    return {
        "schema_name": "observed_icon_inventory_16refs",
        "status": "passed",
        "reference_count": len(ARCHETYPES),
        "observed_icon_count": len(icons),
        "p0_icon_count": sum(1 for icon in icons if icon["priority"] == "P0_REQUIRED_SEMANTIC"),
        "p1_icon_count": sum(1 for icon in icons if icon["priority"] == "P1_HIGH_REUSE"),
        "p2_icon_count": sum(1 for icon in icons if icon["priority"] == "P2_CONTEXTUAL"),
        "p3_icon_count": sum(1 for icon in icons if icon["priority"] == "P3_DECORATIVE_OR_OPTIONAL"),
        "icons": icons,
    }


def summarize_inventory_by_role(inventory: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for icon in inventory["icons"]:
        counts[icon["likely_role"]] = counts.get(icon["likely_role"], 0) + 1
    return dict(sorted(counts.items()))


def _specs_for(archetype: str) -> list[dict[str, Any]]:
    specs: dict[str, list[tuple[str, tuple[float, float, float, float], str]]] = {
        "cover_hero": [
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
            ("calendar", (0.230, 0.905, 0.260, 0.955), "meta_bar"),
            ("user", (0.420, 0.900, 0.455, 0.960), "meta_bar"),
            ("target", (0.895, 0.895, 0.940, 0.965), "footer_action"),
        ],
        "standard_content": [
            ("database", (0.055, 0.235, 0.095, 0.305), "content_card"),
            ("shield", (0.055, 0.465, 0.095, 0.535), "content_card"),
            ("chart_bar", (0.055, 0.695, 0.095, 0.765), "content_card"),
            ("note", (0.780, 0.255, 0.835, 0.345), "insight_rail"),
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
        ],
        "data_dashboard": [
            ("dashboard", (0.020, 0.130, 0.055, 0.190), "header"),
            ("kpi", (0.110, 0.140, 0.145, 0.195), "kpi_card"),
            ("chart_bar", (0.300, 0.400, 0.365, 0.515), "primary_chart"),
            ("pie_chart", (0.705, 0.390, 0.775, 0.510), "secondary_chart"),
            ("filter", (0.330, 0.865, 0.365, 0.920), "footer_filter"),
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
        ],
        "table_heavy": [
            ("table", (0.030, 0.125, 0.060, 0.175), "header_band"),
            ("database", (0.170, 0.130, 0.200, 0.180), "header_icon_zone"),
            ("shield", (0.425, 0.130, 0.455, 0.180), "header_icon_zone"),
            ("warning", (0.760, 0.155, 0.790, 0.205), "side_rail"),
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
        ],
        "section_divider": [
            ("section_marker", (0.018, 0.175, 0.060, 0.255), "section_marker"),
            ("building", (0.030, 0.845, 0.065, 0.910), "source_footer"),
            ("source", (0.035, 0.910, 0.070, 0.970), "source_footer"),
        ],
        "visual_toc": [
            ("target", (0.070, 0.490, 0.130, 0.595), "module_card"),
            ("database", (0.205, 0.490, 0.265, 0.600), "active_module_card"),
            ("network", (0.345, 0.490, 0.405, 0.600), "module_card"),
            ("shield", (0.470, 0.495, 0.525, 0.600), "module_card"),
            ("chart_bar", (0.610, 0.495, 0.670, 0.605), "module_card"),
            ("document", (0.720, 0.495, 0.775, 0.605), "module_card"),
            ("book", (0.860, 0.360, 0.925, 0.475), "right_meta_panel"),
            ("source", (0.030, 0.900, 0.070, 0.965), "source_footer"),
            ("calendar", (0.235, 0.905, 0.265, 0.955), "footer_meta"),
            ("user", (0.425, 0.905, 0.455, 0.960), "footer_meta"),
            ("target", (0.925, 0.895, 0.965, 0.960), "footer_action"),
        ],
        "evidence_overview": [
            ("evidence_trace", (0.040, 0.220, 0.075, 0.285), "evidence_card"),
            ("database", (0.220, 0.220, 0.255, 0.285), "evidence_card"),
            ("chart_bar", (0.400, 0.220, 0.435, 0.285), "evidence_card"),
            ("shield", (0.580, 0.220, 0.615, 0.285), "evidence_card"),
            ("warning", (0.770, 0.220, 0.805, 0.285), "evidence_card"),
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
        ],
        "card_grid": [
            ("database", (0.090, 0.285, 0.125, 0.345), "card_icon_zone"),
            ("shield", (0.305, 0.285, 0.340, 0.345), "card_icon_zone"),
            ("document", (0.520, 0.285, 0.555, 0.345), "card_icon_zone"),
            ("chart_bar", (0.735, 0.285, 0.770, 0.345), "card_icon_zone"),
            ("warning", (0.520, 0.605, 0.555, 0.665), "card_icon_zone"),
            ("scale", (0.735, 0.605, 0.770, 0.665), "card_icon_zone"),
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
        ],
        "methodology_framework": [
            ("layers", (0.130, 0.230, 0.165, 0.285), "framework_row"),
            ("route", (0.130, 0.325, 0.165, 0.380), "framework_row"),
            ("network", (0.130, 0.420, 0.165, 0.475), "framework_row"),
            ("note", (0.780, 0.300, 0.820, 0.365), "side_note_rail"),
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
        ],
        "process_flow": [
            ("process_node", (0.090, 0.365, 0.125, 0.425), "process_node"),
            ("process_node", (0.245, 0.365, 0.280, 0.425), "process_node"),
            ("decision_diamond", (0.520, 0.385, 0.565, 0.455), "decision_gate"),
            ("flag", (0.710, 0.365, 0.745, 0.425), "process_node"),
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
        ],
        "comparison_matrix": [
            ("table", (0.070, 0.270, 0.100, 0.320), "matrix_header"),
            ("scale", (0.820, 0.250, 0.860, 0.320), "decision_rail"),
            ("decision_diamond", (0.820, 0.420, 0.860, 0.485), "decision_rail"),
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
        ],
        "timeline_roadmap": [
            ("timeline", (0.115, 0.285, 0.155, 0.345), "timeline_axis"),
            ("milestone_flag", (0.270, 0.285, 0.310, 0.345), "milestone"),
            ("clock", (0.430, 0.285, 0.470, 0.345), "phase_marker"),
            ("risk_status", (0.760, 0.675, 0.805, 0.735), "risk_row"),
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
        ],
        "decision_record": [
            ("decision_diamond", (0.050, 0.260, 0.095, 0.335), "decision_stamp"),
            ("approval", (0.300, 0.285, 0.335, 0.345), "condition_module"),
            ("file_check", (0.515, 0.285, 0.550, 0.345), "metadata_field"),
            ("evidence_trace", (0.705, 0.710, 0.745, 0.770), "evidence_strip"),
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
        ],
        "risk_register": [
            ("risk_status", (0.090, 0.245, 0.125, 0.295), "risk_row"),
            ("warning", (0.705, 0.245, 0.740, 0.300), "status_column"),
            ("lock", (0.805, 0.245, 0.840, 0.300), "status_column"),
            ("user", (0.875, 0.245, 0.910, 0.300), "owner_column"),
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
        ],
        "case_study": [
            ("note", (0.455, 0.250, 0.490, 0.310), "context_panel"),
            ("evidence_trace", (0.620, 0.455, 0.655, 0.515), "evidence_panel"),
            ("chart_bar", (0.805, 0.455, 0.840, 0.515), "result_panel"),
            ("decision_diamond", (0.805, 0.250, 0.845, 0.315), "decision_panel"),
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
        ],
        "closing_synthesis": [
            ("recommendation", (0.095, 0.300, 0.135, 0.365), "recommendation_module"),
            ("next_action", (0.365, 0.300, 0.405, 0.365), "next_action_module"),
            ("evidence_trace", (0.630, 0.300, 0.670, 0.365), "evidence_summary_module"),
            ("decision_diamond", (0.485, 0.635, 0.530, 0.705), "takeaway_panel"),
            ("source", (0.035, 0.905, 0.070, 0.965), "source_footer"),
        ],
    }
    return [
        {
            "likely_role": role,
            "bbox_norm": list(bbox),
            "component_context": context,
            "container_type": "circle_badge" if role in {"source", "target", "calendar", "user"} else "card_icon_well",
            "priority": "P0_REQUIRED_SEMANTIC" if role in P0_ROLES else "P1_HIGH_REUSE",
        }
        for role, bbox, context in specs[archetype]
    ]
