"""Archetype-specific visual identity checks for E03-VQ."""

from __future__ import annotations

from collections import Counter
from typing import Any


def evaluate_archetype_visual_identity(archetype_id: str, roles: list[str], metrics: dict[str, Any]) -> dict[str, Any]:
    counts = Counter(roles)
    checks = _checks_for(archetype_id, counts, metrics)
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "schema_name": "archetype_visual_identity",
        "archetype_id": archetype_id,
        "status": "passed" if not failures else "failed",
        "identity_checks": checks,
        "role_counts": dict(sorted(counts.items())),
        "metrics": metrics,
        "failures": failures,
        "canva_parity_claimed": False,
    }


def build_archetype_visual_identity_report(items: list[dict[str, Any]]) -> dict[str, Any]:
    reports = {
        item["archetype_id"]: evaluate_archetype_visual_identity(
            item["archetype_id"],
            item.get("roles", []),
            item.get("metrics", {}),
        )
        for item in items
    }
    failures = [f"{archetype_id}:{failure}" for archetype_id, report in reports.items() for failure in report["failures"]]
    return {
        "schema_name": "archetype_visual_identity_report",
        "status": "passed" if not failures else "failed",
        "archetypes": reports,
        "failures": failures,
        "canva_parity_claimed": False,
    }


def _checks_for(archetype_id: str, counts: Counter[str], metrics: dict[str, Any]) -> dict[str, bool]:
    connector_count = int(metrics.get("connector_count", metrics.get("connector_vector_count", 0)))
    motif_count = int(metrics.get("decorative_motif_count", 0))
    media_count = int(metrics.get("media_count", 0))
    chart_count = int(metrics.get("chart_count", 0))
    table_count = int(metrics.get("table_count", 0))
    accent_count = int(metrics.get("accent_shape_count", 0))
    placeholder_ratio = float(metrics.get("placeholder_ratio", metrics.get("placeholder_text_ratio", 0.0)))
    checks: dict[str, bool]
    if archetype_id == "cover_hero":
        checks = {
            "hero_visual_identity": counts["hero_visual_field"] >= 1 and (media_count >= 1 or accent_count >= 2),
            "title_subtitle_hierarchy": counts["title_text_region"] >= 1 and counts["subtitle_text_region"] >= 1,
            "premium_visual_motif": motif_count + connector_count + accent_count >= 3,
            "footer_meta_system": counts["source_footer_strip"] >= 1 or counts["source_footer_text"] >= 1,
        }
    elif archetype_id == "section_divider":
        checks = {
            "section_transition_identity": counts["section_title_text_region"] >= 1 or counts["title_text_region"] >= 1,
            "large_section_marker": counts["section_number_text_region"] >= 1 or counts["section_label_text_region"] >= 1,
            "strong_visual_divider": connector_count + motif_count >= 1,
            "not_generic_content_slide": counts["card_panel"] < 3,
        }
    elif archetype_id == "visual_toc":
        nav_item_count = counts["navigation_item_text_region"] + counts["navigation_item_panel"] + counts["toc_item"] + counts["toc_text_region"]
        checks = {
            "navigation_item_system": nav_item_count >= 4,
            "active_current_marker": counts["active_marker"] >= 1,
            "not_generic_card_grid": nav_item_count >= counts["card_panel"],
        }
    elif archetype_id == "standard_content":
        checks = {
            "three_to_four_content_slots": counts["card_panel"] >= 3 or counts["body_text_region"] >= 3,
            "premium_card_treatment": counts["card_underline"] >= 3 or accent_count >= 3,
            "standard_content_supporting_motif_missing": connector_count + motif_count + counts["semantic_icon"] >= 1,
            "footer_source_system": counts["source_footer_strip"] >= 1 or counts["source_footer_text"] >= 1,
        }
    elif archetype_id == "evidence_overview":
        checks = {
            "claim_evidence_hierarchy": counts["key_claim_text_region"] >= 1 and counts["evidence_card"] >= 3,
            "citation_source_affordance": counts["source_footer_strip"] >= 1 or counts["source_footer_text"] >= 1,
            "evidence_card_structure": counts["evidence_card"] >= 3,
        }
    elif archetype_id == "card_grid":
        card_count = counts["card_panel"] + counts["grid_card"]
        checks = {
            "organized_grid": card_count >= 4,
            "card_variation_or_icon_affordance": counts["semantic_icon"] >= 1 or motif_count + connector_count >= 1,
            "not_blank_repeated_rectangles": placeholder_ratio < 0.72,
        }
    elif archetype_id == "methodology_framework":
        checks = {
            "framework_pillar_identity": counts["framework_stage"] >= 3 or counts["process_node"] >= 3,
            "grouping_connector_logic": connector_count >= 2,
            "not_generic_cards_only": counts["card_panel"] < counts["framework_stage"] + counts["process_node"] + 2,
        }
    elif archetype_id == "process_flow":
        checks = {
            "directional_flow": connector_count >= 3,
            "process_sequence_identity": counts["process_node"] >= 4,
            "connector_emphasis": connector_count >= max(1, counts["process_node"] - 2),
        }
    elif archetype_id == "comparison_matrix":
        checks = {
            "matrix_table_identity": counts["comparison_matrix"] >= 1 and table_count >= 1,
            "row_column_hierarchy": counts["matrix_header_band"] >= 1 or table_count >= 1,
            "not_generic_grid_only": table_count >= 1,
        }
    elif archetype_id == "data_dashboard":
        checks = {
            "dashboard_identity": counts["kpi_card"] >= 3 and counts["primary_chart"] >= 1,
            "chart_prominence": chart_count >= 1 or counts["primary_chart"] >= 1,
            "insight_hierarchy": counts["insight_panel"] >= 1 or counts["insight_text_region"] >= 1,
        }
    elif archetype_id == "table_heavy":
        checks = {
            "dense_table_identity": counts["table_region"] >= 1 and table_count >= 1,
            "header_body_hierarchy": counts["table_header_band"] >= 1 or table_count >= 1,
            "table_readability": table_count >= 1 and placeholder_ratio < 0.8,
        }
    elif archetype_id == "timeline_roadmap":
        checks = {
            "timeline_phase_rail": counts["timeline_axis"] >= 1 or counts["phase_rail"] >= 1,
            "milestone_sequence": counts["milestone_text_region"] >= 4 or counts["timeline_phase"] >= 4,
            "not_generic_card_row_only": connector_count >= 1,
        }
    else:
        checks = {"known_archetype": False}
    return checks
