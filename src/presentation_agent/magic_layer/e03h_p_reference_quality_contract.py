"""Premium reference quality contract v2 for E03H-P."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e03h_p_reference_strength_score import score_reference_strength


def build_premium_reference_quality_contract_v2() -> dict[str, Any]:
    return {
        "schema_name": "premium_reference_quality_contract_v2",
        "status": "active",
        "core_rules": [
            "must_not_look_like_wireframe",
            "must_have_clear_focal_object",
            "must_have_visible_archetype_identity",
            "must_have_meaningful_visual_backplates",
            "must_preserve_protected_text_zones",
            "must_not_place_semantic_text_inside_photo_fields",
            "must_not_use_unreadable_microtext",
            "must_not_be_generic_dark_background_plus_empty_boxes",
        ],
        "pass_threshold": 0.72,
        "reference_specific_rules": {
            "cover_hero_photo_editorial": ["strong_hero_photo_editorial_visual_field", "protected_title_subtitle_meta"],
            "standard_content_card_cluster": ["three_or_four_rich_card_panels", "icon_accent_chrome_backplate_treatment"],
            "evidence_stack_visual": ["claim_focal_region", "three_plus_evidence_cards", "claim_evidence_source_hierarchy"],
            "comparison_matrix_hybrid": ["matrix_table_identity", "row_column_header_hierarchy", "native_editable_matrix"],
            "methodology_framework_layered": ["layered_framework_stack_identity", "stage_labels_and_connectors"],
            "timeline_roadmap_hybrid": ["timeline_rail", "milestones_labels_phase_hierarchy"],
            "visual_toc_navigation": ["navigation_items", "active_current_marker", "section_rhythm"],
            "photo_caption_grid_hybrid": ["bounded_photo_image_frames", "editable_captions", "non_empty_visual_fields"],
        },
        "canva_parity_claimed": False,
    }


def evaluate_premium_reference_quality_contract_v2(payload: dict[str, Any], contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = contract or build_premium_reference_quality_contract_v2()
    score = score_reference_strength(payload)
    passed = score["status"] == "passed"
    return {
        "schema_name": "premium_reference_quality_contract_v2_evaluation",
        "status": "passed" if passed else "failed",
        "reference_id": payload["reference_id"],
        "all_core_rules_pass": passed,
        "reference_strength_score": score["reference_strength_score"],
        "pass_threshold": contract["pass_threshold"],
        "failures": score["failures"],
        "contract_rules": contract["core_rules"],
        "canva_parity_claimed": False,
    }


def premium_reference_quality_contract_markdown(report: dict[str, Any]) -> str:
    lines = ["# Premium Reference Quality Contract V2", "", f"- Status: `{report.get('status', 'active')}`", "- Broad Canva parity claimed: `False`", ""]
    for rule in report.get("core_rules", []):
        lines.append(f"- {rule}")
    return "\n".join(lines)
