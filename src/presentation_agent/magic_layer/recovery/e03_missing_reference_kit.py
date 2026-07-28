from __future__ import annotations

from pathlib import Path
from typing import Any

from .e03_reference_contract import CORE_ARCHETYPES, EXPANSION_ARCHETYPES


EXPECTED_ARCHETYPES = [*CORE_ARCHETYPES, *EXPANSION_ARCHETYPES]
CORE_REQUIRED_SEMANTICS = {
    "cover_hero": ["cover/hero layout", "title region"],
    "standard_content": ["title/body/card/bullet/panel structure"],
    "data_dashboard": ["KPI cards/values/labels", "chart/dashboard region", "not generic card-only slide"],
    "table_heavy": ["table/grid/header/body cell structure", "not generic card-only slide"],
}
EXPANSION_REQUIRED_SEMANTICS = {
    "executive_summary": ["summary/insight structure"],
    "section_divider": ["section/divider title structure"],
    "two_column_comparison": ["left/right comparison structure"],
    "three_card_insight": ["three distinct card/insight regions"],
    "process_timeline": ["timeline/process steps/connectors"],
    "framework_2x2_matrix": ["visible 2x2 matrix/framework"],
    "chart_focus": ["chart-centered visual structure"],
    "appendix_reference": ["reference/table/text-heavy appendix structure"],
    "image_story": ["image-led story with caption/callout or narrative structure"],
    "quote_pullout": ["quote and attribution structure"],
    "case_study": ["case/story/panel/metric structure"],
    "roadmap_milestones": ["roadmap/milestone structure"],
}
SEMANTIC_REQUIREMENTS = {**CORE_REQUIRED_SEMANTICS, **EXPANSION_REQUIRED_SEMANTICS}
FORBIDDEN_SOURCES = [
    "P03_RENDER",
    "P04_RENDER",
    "P05_RENDER",
    "P06_CONTACT_SHEET",
    "B01_OVERLAY",
    "C03A_RENDER",
    "SCREENSHOT",
    "CONTACT_SHEET",
    "POWERPOINT_EXPORTED_SLIDE",
    "GENERATED_FLOOD",
    "QUARANTINE_UNREGISTERED",
    "OLD_OUTPUT_ARTIFACT",
    "CANONICAL_OUTPUT",
]
FORBIDDEN_FILENAME_TOKENS = ["render", "overlay", "contact_sheet", "screenshot", "comparison", "preview"]


def build_manual_reference_placement_kit(missing_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "e03_manual_reference_placement_kit_report.v1",
        "missing_count": len(missing_rows),
        "placements": [
            {
                "archetype_id": row["archetype_id"],
                "expected_path": row["expected_path"],
                "file_naming_rule": "{archetype_id}.png under design_runs/run_004/inputs/e03_rx/references/",
                "dimension_rule": "16:9 preferred, 1920x1080 preferred",
                "provenance_required": True,
                "semantic_notes_required_in_registry": True,
            }
            for row in missing_rows
        ],
        "forbidden_sources": ["renders", "contact sheets", "generated flood images", "quarantine", "canonical artifacts"],
        "do_not_create_fake_references": True,
        "product_pass": False,
    }


def build_rv01a_manual_placement_kit(run_folder: str | Path) -> dict[str, Any]:
    run = Path(run_folder)
    placements = [_placement_row(run, archetype) for archetype in EXPECTED_ARCHETYPES]
    return {
        "schema": "missing_reference_placement_plan.v1",
        "mode": "E03_REFERENCE_MANUAL_PLACEMENT_KIT",
        "placements": placements,
        "missing_count": len(placements),
        "image_files_created": 0,
        "generates_pptx": False,
        "next_validation_stage": "RV01_RERUN",
        "product_pass": False,
    }


def build_dropzone_manifest(run_folder: str | Path) -> dict[str, Any]:
    run = Path(run_folder)
    dropzone = run / "inputs/e03_rx/references"
    return {
        "schema": "manual_reference_dropzone_manifest.v1",
        "dropzone_path": str(dropzone),
        "expected_reference_count": len(EXPECTED_ARCHETYPES),
        "expected_filenames": [f"{archetype}.png" for archetype in EXPECTED_ARCHETYPES],
        "do_not_create_images_in_rv01a": True,
        "product_pass": False,
    }


def build_filename_contract() -> dict[str, Any]:
    return {
        "schema": "e03_reference_filename_contract.v1",
        "preferred_extension": ".png",
        "rules": {
            "lowercase_snake_case": True,
            "spaces_allowed": False,
            "suffixes_forbidden": ["_copy", "_final", "_render", "_screenshot", "_contact_sheet"],
            "multiple_candidates_allowed": False,
        },
        "expected_filenames": [f"{archetype}.png" for archetype in EXPECTED_ARCHETYPES],
        "wrong_filename_decisions": ["UNEXPECTED_DUPLICATE", "WRONG_EXTENSION", "MANUAL_REVIEW_REQUIRED"],
        "product_pass": False,
    }


def build_dimension_contract() -> dict[str, Any]:
    return {
        "schema": "e03_reference_dimension_contract.v1",
        "preferred_dimensions": {"width": 1920, "height": 1080},
        "preferred_aspect_ratio": "16:9",
        "allowed_minimum_dimensions": {"width": 1280, "height": 720},
        "disallowed": ["portrait", "square", "tiny images", "unreadable images", "contact sheets", "multi-slide composites"],
        "rv01_rerun_decisions": [
            "DIMENSION_PASS",
            "DIMENSION_PASS_WITH_LIMITATION",
            "DIMENSION_FAIL_NOT_16_9",
            "DIMENSION_FAIL_TOO_SMALL",
            "DIMENSION_FAIL_UNREADABLE",
            "DIMENSION_MANUAL_REVIEW_REQUIRED",
        ],
        "product_pass": False,
    }


def build_provenance_contract() -> dict[str, Any]:
    return {
        "schema": "e03_reference_provenance_contract.v1",
        "required_fields": [
            "source_type",
            "source_note",
            "created_by_or_supplied_by",
            "not_generated_flood_confirmed",
            "not_render_output_confirmed",
            "not_contact_sheet_confirmed",
        ],
        "optional_fields": ["created_at_or_received_at", "original_path", "license_or_usage_note", "semantic_assertion_author"],
        "allowed_source_types": ["MANUAL_REFERENCE_IMAGE", "DESIGN_TOOL_REFERENCE", "APPROVED_EXISTING_REFERENCE", "PRIOR_CORE_REFERENCE_IMPORTED"],
        "forbidden_source_types": [
            "UNKNOWN",
            "RENDER_OUTPUT",
            "CONTACT_SHEET",
            "B01_OVERLAY",
            "P05_RENDER",
            "P06_CONTACT_SHEET",
            "GENERATED_FLOOD",
            "QUARANTINE_UNREGISTERED",
            "CANONICAL_OUTPUT",
            "SCREENSHOT_OF_PPTX",
        ],
        "missing_provenance_decision": "MANUAL_REVIEW_REQUIRED_OR_INVALID_SOURCE",
        "product_pass": False,
    }


def build_semantic_assertion_template() -> dict[str, Any]:
    return {
        "schema": "e03_manual_semantic_assertion_template.v1",
        "archetype_id": None,
        "reference_filename": None,
        "semantic_assertion_status": "NOT_ASSERTED",
        "asserted_by": None,
        "assertion_date": None,
        "required_semantic_elements_present": [],
        "prohibited_generic_slide_confirmed": False,
        "notes": "",
        "confidence": "low",
        "ready_for_rv01_validation": False,
        "per_archetype_required_semantic_elements": SEMANTIC_REQUIREMENTS,
        "rv01a_uses_ocr": False,
        "rv01a_inferrs_pixels": False,
        "product_pass": False,
    }


def build_semantic_assertion_contract() -> dict[str, Any]:
    return {
        "schema": "e03_reference_semantic_assertion_contract.v1",
        "allowed_statuses": ["ASSERTED", "NOT_ASSERTED", "NEEDS_REVIEW"],
        "template": build_semantic_assertion_template(),
        "manual_assertion_required_for_expansion": True,
        "ocr_allowed": False,
        "pixel_inference_allowed": False,
        "product_pass": False,
    }


def build_forbidden_reference_source_contract() -> dict[str, Any]:
    return {
        "schema": "e03_forbidden_reference_source_contract.v1",
        "forbidden_sources": FORBIDDEN_SOURCES,
        "forbidden_filename_tokens": FORBIDDEN_FILENAME_TOKENS,
        "rv01_rerun_block_decisions": [
            "FORBIDDEN_RENDER_OR_CONTACT_SHEET",
            "FORBIDDEN_GENERATED_FLOOD",
            "FORBIDDEN_OUTPUT_ARTIFACT",
            "INVALID_SOURCE",
        ],
        "rv01a_may_copy_forbidden_sources": False,
        "product_pass": False,
    }


def build_manual_placement_checklist(run_folder: str | Path) -> dict[str, Any]:
    run = Path(run_folder)
    return {
        "schema": "e03_reference_manual_placement_checklist.v1",
        "dropzone_path": str(run / "inputs/e03_rx/references"),
        "items": [
            {
                "archetype_id": archetype,
                "expected_filename": f"{archetype}.png",
                "file_placed": False,
                "correct_filename": False,
                "is_16_9": False,
                "provenance_filled": False,
                "semantic_assertion_filled": False,
                "forbidden_source_checked": False,
                "ready_for_rv01_rerun": False,
            }
            for archetype in EXPECTED_ARCHETYPES
        ],
        "product_pass": False,
    }


def build_core_reference_reuse_guidance(prior_hashes: dict[str, str | None] | None = None) -> dict[str, Any]:
    prior_hashes = prior_hashes or {}
    return {
        "schema": "e03_core_reference_reuse_guidance.v1",
        "core_references": [
            {
                "archetype_id": archetype,
                "expected_filename": f"{archetype}.png",
                "prior_hash": prior_hashes.get(archetype),
                "prior_evidence_stage": "P05/P06/C05",
                "prior_evidence_path": "design_runs/run_003/outputs/p05_rx_four_core_pipeline_v2_regression_e02_references/four_core_reference_hash_validation.json",
                "required_semantic_elements": SEMANTIC_REQUIREMENTS[archetype],
                "copy_guidance": "Operator may manually copy the same approved core reference into run_004; RV01 rerun must verify hash.",
                "active_reference_required": True,
            }
            for archetype in CORE_ARCHETYPES
        ],
        "rv01a_copies_references": False,
        "product_pass": False,
    }


def build_expansion_reference_requirements() -> dict[str, Any]:
    return {
        "schema": "e03_expansion_reference_requirements.v1",
        "current_valid_count": 0,
        "minimum_valid_required": 8,
        "full_valid_required": 12,
        "references": [
            {
                "archetype_id": archetype,
                "expected_filename": f"{archetype}.png",
                "expected_semantic_elements": SEMANTIC_REQUIREMENTS[archetype],
                "forbidden_generic_substitutes": ["generic card slide", "wrong specialized structure", "unreadable placeholder board"],
                "dimension_requirement": "16:9, preferred 1920x1080, minimum 1280x720 if policy permits",
                "provenance_required": True,
                "semantic_assertion_required": True,
                "readiness_effect": "counts toward minimum mode if valid; required for full mode",
            }
            for archetype in EXPANSION_ARCHETYPES
        ],
        "product_pass": False,
    }


def build_readiness_rerun_checklist() -> dict[str, Any]:
    return {
        "schema": "e03_reference_readiness_rerun_checklist.v1",
        "before_rv01_rerun": [
            "run_004 reference folder has images",
            "registry updated",
            "minimum or full target selected",
            "no forbidden sources",
            "semantic assertions present",
            "no E03 run started",
            "no PPTX generated",
            "E04/D08 blocked",
        ],
        "minimum_mode_result": "4 core + 8 expansion valid allows explicit E03-RV prompt",
        "full_mode_result": "4 core + 12 expansion valid allows explicit E03-RV-FULL prompt",
        "missing_result": "RV01A/manual placement continues",
        "semantic_missing_result": "RV01B may start",
        "product_pass": False,
    }


def build_archetype_kit(run_folder: str | Path, archetype: str) -> dict[str, Any]:
    run = Path(run_folder)
    return {
        "schema": "rv01a_archetype_kit.v1",
        "archetype_id": archetype,
        "expected_filename": f"{archetype}.png",
        "expected_path": str(run / "inputs/e03_rx/references" / f"{archetype}.png"),
        "group": "core" if archetype in CORE_ARCHETYPES else "expansion",
        "required_for_minimum": archetype in CORE_ARCHETYPES or archetype in EXPANSION_ARCHETYPES[:8],
        "required_for_full": True,
        "required_semantic_elements": SEMANTIC_REQUIREMENTS[archetype],
        "dimension_requirement": "16:9, preferred 1920x1080",
        "provenance_required": True,
        "semantic_assertion_required": True,
        "default_semantic_assertion_status": "NOT_ASSERTED",
        "product_pass": False,
    }


def _placement_row(run: Path, archetype: str) -> dict[str, Any]:
    return {
        "archetype_id": archetype,
        "expected_filename": f"{archetype}.png",
        "expected_path": str(run / "inputs/e03_rx/references" / f"{archetype}.png"),
        "current_status": "MISSING",
        "required_for_minimum": archetype in CORE_ARCHETYPES or archetype in EXPANSION_ARCHETYPES[:8],
        "required_for_full": True,
        "placement_required": True,
        "semantic_assertion_required": True,
        "provenance_required": True,
        "dimension_requirement": "16:9 preferred, 1920x1080 preferred, minimum 1280x720 if policy permits",
        "forbidden_source_reminder": "Do not use renders, overlays, contact sheets, screenshots, generated flood, quarantine, output, or canonical artifacts.",
        "next_validation_stage": "RV01_RERUN",
    }
