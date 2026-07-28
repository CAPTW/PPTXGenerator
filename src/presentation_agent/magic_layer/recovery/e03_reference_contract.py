from __future__ import annotations

from typing import Any


CORE_ARCHETYPES = ["cover_hero", "standard_content", "data_dashboard", "table_heavy"]
EXPANSION_ARCHETYPES = [
    "executive_summary",
    "section_divider",
    "two_column_comparison",
    "three_card_insight",
    "process_timeline",
    "framework_2x2_matrix",
    "chart_focus",
    "appendix_reference",
    "image_story",
    "quote_pullout",
    "case_study",
    "roadmap_milestones",
]

SEMANTIC_REQUIREMENTS = {
    "chart_focus": "chart-like content with editable chart/label intent",
    "appendix_reference": "table/text-heavy appendix structure where applicable",
    "process_timeline": "timeline or process structure",
    "framework_2x2_matrix": "matrix structure",
    "roadmap_milestones": "milestone or roadmap structure",
}


def build_e03_reference_readiness_contract() -> dict[str, Any]:
    return {
        "schema": "e03_reference_readiness_contract.v1",
        "readiness_levels": [
            "CORE_REFERENCE_VALIDATED_BY_P05",
            "EXPANSION_REFERENCE_PRESENT_NOT_VALIDATED",
            "EXPANSION_REFERENCE_VALIDATED",
            "MISSING",
            "INVALID_DIMENSION",
            "INVALID_SOURCE",
            "INVALID_SEMANTIC_CONTENT",
            "FORBIDDEN_RENDER_OR_CONTACT_SHEET",
            "FORBIDDEN_GENERATED_FLOOD",
        ],
        "future_modes": {
            "E03_MINIMUM_12_ARCHETYPE_MODE": {"core_required": 4, "valid_expansion_required": 8, "total_required": 12},
            "E03_FULL_16_ARCHETYPE_MODE": {"core_required": 4, "valid_expansion_required": 12, "total_required": 16},
        },
        "reference_requirements": {
            "supported_formats": ["png", "jpg", "jpeg", "webp"],
            "preferred_aspect_ratio": "16:9",
            "preferred_dimensions": "1920x1080",
            "provenance_required": True,
            "active_registered_input_required": True,
            "render_output_allowed": False,
            "contact_sheet_allowed": False,
            "generated_flood_allowed": False,
            "quarantine_allowed_without_explicit_restore": False,
        },
        "rv00_validates_actual_images": False,
        "rv01_e03a_validation_required": True,
        "product_pass": False,
    }


def build_e03_archetype_reference_contract() -> dict[str, Any]:
    archetypes: dict[str, Any] = {}
    for archetype in CORE_ARCHETYPES:
        archetypes[archetype] = {
            "group": "core",
            "initial_status": "CORE_VALIDATED_IN_PRIOR_RUN_NEEDS_RV01_REGISTRY_CONFIRMATION",
            "semantic_requirement": SEMANTIC_REQUIREMENTS.get(archetype, "core four reference semantics from P05/P06"),
        }
    for archetype in EXPANSION_ARCHETYPES:
        archetypes[archetype] = {
            "group": "expansion",
            "initial_status": "MISSING_OR_NOT_VALIDATED",
            "semantic_requirement": SEMANTIC_REQUIREMENTS.get(archetype, f"{archetype} specialized slide structure"),
        }
    return {
        "schema": "e03_archetype_reference_contract.v1",
        "core_archetypes": CORE_ARCHETYPES,
        "expansion_archetypes": EXPANSION_ARCHETYPES,
        "archetypes": archetypes,
        "archetype_count": len(archetypes),
        "product_pass": False,
    }


def build_e03_reference_source_policy() -> dict[str, Any]:
    return {
        "schema": "e03_reference_source_policy.v1",
        "allowed_sources": ["active_run_004_registered_input", "explicit_future_manual_reference_candidate"],
        "forbidden_sources": [
            "generated_flood",
            "render_output",
            "contact_sheet",
            "canonical_artifact",
            "source_bound_deck",
            "quarantine_without_explicit_restore",
            "old_output_artifact_as_reference",
        ],
        "copy_old_references_in_rv00": False,
        "product_pass": False,
    }


def build_e03_reference_validation_gate_spec() -> dict[str, Any]:
    return {
        "schema": "e03_reference_validation_gate_spec.v1",
        "gate_sequence": [
            "registry_presence_check",
            "file_exists_check",
            "format_dimension_check",
            "source_policy_check",
            "render_contact_sheet_flood_rejection",
            "semantic_archetype_check",
            "hash_provenance_recording",
            "readiness_decision",
        ],
        "fatal_failures": [
            "MISSING",
            "INVALID_DIMENSION",
            "INVALID_SOURCE",
            "INVALID_SEMANTIC_CONTENT",
            "FORBIDDEN_RENDER_OR_CONTACT_SHEET",
            "FORBIDDEN_GENERATED_FLOOD",
        ],
        "rv00_executes_gate": False,
        "rv01_executes_gate": True,
        "product_pass": False,
    }
