"""Archetype identity gate for D06.1 visual fidelity recalibration."""

from __future__ import annotations

from typing import Any


def archetype_major_region_requirements_v2() -> dict[str, Any]:
    requirements = {
        "cover_hero": ["title_cluster", "hero_visual_field", "meta_strip", "bottom_footer_source_strip"],
        "standard_content": ["title_cluster", "card_panel_group", "right_side_rail", "bottom_footer_source_strip"],
        "data_dashboard": ["kpi_row", "chart_frame", "right_side_rail", "bottom_footer_source_strip"],
        "table_heavy": ["title_cluster", "table_frame", "right_side_rail", "bottom_footer_source_strip"],
        "section_divider": ["section_number", "title_cluster", "chapter_marker", "bottom_footer_source_strip"],
        "visual_toc": ["navigation_modules", "active_path", "side_meta_rail", "bottom_footer_source_strip"],
        "evidence_overview": ["evidence_cards", "confidence_module", "bottom_insight_strip", "bottom_footer_source_strip"],
        "card_grid": ["multi_card_grid", "category_labels", "insight_strip", "bottom_footer_source_strip"],
        "methodology_framework": ["framework_layers", "connectors", "side_note", "bottom_footer_source_strip"],
        "process_flow": ["process_nodes", "connectors", "decision_points", "note_rail", "bottom_footer_source_strip"],
        "comparison_matrix": ["matrix_grid", "option_headers", "decision_rail", "bottom_footer_source_strip"],
        "timeline_roadmap": ["timeline_line", "phases", "milestones", "bottom_footer_source_strip"],
        "decision_record": ["decision_stamp", "record_panel", "status_modules", "evidence_strip", "bottom_footer_source_strip"],
        "risk_register": ["register_table", "severity_status_fields", "side_meta_rail", "bottom_footer_source_strip"],
        "case_study": ["image_frame", "context_panel", "evidence_panel", "result_panel", "bottom_footer_source_strip"],
        "closing_synthesis": ["recommendation", "next_action", "evidence_summary", "decision_takeaway", "bottom_footer_source_strip"],
    }
    return {
        "schema_name": "archetype_major_region_requirements_v2",
        "status": "recorded",
        "requirements": requirements,
        "canva_parity_claimed": False,
    }


def expansion_archetype_identity_policy_v1() -> dict[str, Any]:
    return {
        "schema_name": "expansion_archetype_identity_policy_v1",
        "status": "recorded",
        "policy": {
            "structural_editability_is_not_sufficient": True,
            "generic_white_block_regression_blocks_D07": True,
            "placeholder_marker_dominance_blocks_D07": True,
            "archetype_specific_component_required": True,
            "expansion_archetype_cannot_collapse_to_standard_content": True,
        },
        "canva_parity_claimed": False,
    }


def evaluate_archetype_identity(spec: dict[str, Any], placeholder_report: dict[str, Any]) -> dict[str, Any]:
    reference_id = str(spec.get("reference_id"))
    required = (archetype_major_region_requirements_v2()["requirements"]).get(reference_id, [])
    objects = spec.get("objects") or []
    covered = {
        obj.get("identity_region")
        for obj in objects
        if obj.get("identity_region")
    }
    component_types = {
        obj.get("component_identity")
        for obj in objects
        if obj.get("component_identity")
    }
    missing = sorted(set(required).difference(covered))
    generic_blocks = [obj for obj in objects if obj.get("generic_white_block")]
    identity_specific = len(component_types.difference({None, "generic_panel"})) >= 2
    status = "passed" if not missing and not generic_blocks and identity_specific and placeholder_report.get("status") == "passed" else "failed"
    return {
        "schema_name": "d06_1_archetype_identity_report",
        "reference_id": reference_id,
        "status": status,
        "required_identity_regions": required,
        "covered_identity_regions": sorted(item for item in covered if item),
        "missing_identity_regions": missing,
        "component_identity_count": len([item for item in component_types if item]),
        "reference_chrome_preserved": "bottom_footer_source_strip" in covered,
        "generic_white_block_count": len(generic_blocks),
        "placeholder_clutter_status": placeholder_report.get("status"),
        "d07_blocking": status != "passed",
    }


def batch_visual_fidelity_rubric_v2() -> dict[str, Any]:
    return {
        "schema_name": "batch_visual_fidelity_rubric_v2",
        "status": "recorded",
        "fail_conditions": [
            "generic_empty_white_block_rendering",
            "overuse_of_placeholder_diamonds",
            "missing_major_content_region",
            "missing_source_footer_strip",
            "missing_archetype_specific_component",
            "sparse_debug_overlay_style",
            "reference_vs_render_mismatch_hidden_by_structural_pass",
            "core4_regression_from_D05_1",
            "expansion_archetype_collapse_into_standard_content_or_card_grid",
        ],
        "score_dimensions": [
            "archetype_identity",
            "major_region_coverage",
            "composition_alignment",
            "chrome_preservation",
            "component_specificity",
            "slot_usability",
            "source_footer_integration",
            "visual_density_control",
            "semantic_editability",
            "no_raster_cheat",
            "D07_readiness",
        ],
        "canva_parity_claimed": False,
    }
