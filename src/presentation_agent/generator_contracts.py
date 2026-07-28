"""Schema-first validation utilities for generator-facing artifacts.

These contracts are intentionally separate from the existing runtime state
schemas so the new design/template pipeline can grow without changing the
current PPTX compiler inputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schemas"

GENERATOR_SCHEMA_FILES: dict[str, str] = {
    "presentation_plan": "presentation_plan.schema.json",
    "slide_blueprint": "slide_blueprint.schema.json",
    "design_brief": "design_brief.schema.json",
    "extracted_design_system": "extracted_design_system.schema.json",
    "editable_template_spec": "editable_template_spec.schema.json",
    "editable_template_spec_patch": "editable_template_spec_patch.schema.json",
    "deck_assembly_plan": "deck_assembly_plan.schema.json",
    "presentation_architecture": "presentation_architecture.schema.json",
    "creative_template_architecture": "creative_template_architecture.schema.json",
    "slide_semantic_sidecar": "slide_semantic_sidecar.schema.json",
    "slide_title": "slide_title.schema.json",
    "slide_subtitle": "slide_subtitle.schema.json",
    "slide_body_blocks": "slide_body_blocks.schema.json",
    "slide_cards": "slide_cards.schema.json",
    "slide_chart_data": "slide_chart_data.schema.json",
    "slide_table_data": "slide_table_data.schema.json",
    "slide_image_needs": "slide_image_needs.schema.json",
    "slide_speaker_notes": "slide_speaker_notes.schema.json",
    "slide_citations": "slide_citations.schema.json",
    "extracted_design_board_codex": "extracted_design_board_codex.schema.json",
    "extracted_slide_archetypes": "extracted_slide_archetypes.schema.json",
    "extracted_component_library": "extracted_component_library.schema.json",
    "extracted_style_tokens": "extracted_style_tokens.schema.json",
}

__all__ = [
    "ContractValidationResult",
    "GENERATOR_SCHEMA_FILES",
    "discover_generator_contract_samples",
    "infer_generator_schema_name",
    "load_generator_schema",
    "schema_path_for",
    "validateDeckAssemblyPlan",
    "validatePresentationArchitecture",
    "validateCreativeTemplateArchitecture",
    "validateSlideSemanticSidecar",
    "validateDesignBrief",
    "validateEditableTemplateSpec",
    "validateEditableTemplateSpecPatch",
    "validateExtractedDesignSystem",
    "validateExtractedDesignBoardCodex",
    "validateExtractedSlideArchetypes",
    "validateExtractedComponentLibrary",
    "validateExtractedStyleTokens",
    "validatePresentationPlan",
    "validateSlideBodyBlocks",
    "validateSlideBlueprint",
    "validateSlideCards",
    "validateSlideChartData",
    "validateSlideCitations",
    "validateSlideImageNeeds",
    "validateSlideSpeakerNotes",
    "validateSlideSubtitle",
    "validateSlideTableData",
    "validateSlideTitle",
    "validate_generator_contract_file",
    "validate_generator_contract_payload",
]


@dataclass(frozen=True, slots=True)
class ContractValidationResult:
    schema_name: str
    path: Path | None
    valid: bool
    errors: tuple[str, ...] = ()


def validatePresentationPlan(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("presentation_plan", payload)


def validateSlideBlueprint(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("slide_blueprint", payload)


def validateSlideTitle(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("slide_title", payload)


def validateSlideSubtitle(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("slide_subtitle", payload)


def validateSlideBodyBlocks(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("slide_body_blocks", payload)


def validateSlideCards(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("slide_cards", payload)


def validateSlideChartData(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("slide_chart_data", payload)


def validateSlideTableData(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("slide_table_data", payload)


def validateSlideImageNeeds(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("slide_image_needs", payload)


def validateSlideSpeakerNotes(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("slide_speaker_notes", payload)


def validateSlideCitations(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("slide_citations", payload)


def validateDesignBrief(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("design_brief", payload)


def validateExtractedDesignSystem(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("extracted_design_system", payload)


def validateEditableTemplateSpec(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("editable_template_spec", payload)


def validateEditableTemplateSpecPatch(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("editable_template_spec_patch", payload)


def validateDeckAssemblyPlan(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("deck_assembly_plan", payload)


def validatePresentationArchitecture(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("presentation_architecture", payload)


def validateCreativeTemplateArchitecture(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("creative_template_architecture", payload)


def validateSlideSemanticSidecar(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("slide_semantic_sidecar", payload)


def validateExtractedDesignBoardCodex(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("extracted_design_board_codex", payload)


def validateExtractedSlideArchetypes(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("extracted_slide_archetypes", payload)


def validateExtractedComponentLibrary(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("extracted_component_library", payload)


def validateExtractedStyleTokens(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_generator_contract_payload("extracted_style_tokens", payload)


def load_generator_schema(schema_name: str) -> dict[str, Any]:
    schema_path = schema_path_for(schema_name)
    return json.loads(schema_path.read_text(encoding="utf-8"))


def schema_path_for(schema_name: str) -> Path:
    filename = GENERATOR_SCHEMA_FILES.get(schema_name)
    if filename is None:
        raise ValueError(f"unknown generator contract schema: {schema_name}")
    path = SCHEMA_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def validate_generator_contract_payload(schema_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    schema = load_generator_schema(schema_name)
    validator = Draft202012Validator(schema)
    validator.validate(payload)
    return payload


def validate_generator_contract_file(schema_name: str, path: str | Path) -> ContractValidationResult:
    artifact_path = Path(path)
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        validate_generator_contract_payload(schema_name, payload)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        return ContractValidationResult(
            schema_name=schema_name,
            path=artifact_path,
            valid=False,
            errors=(str(exc),),
        )
    return ContractValidationResult(schema_name=schema_name, path=artifact_path, valid=True)


def infer_generator_schema_name(path: str | Path) -> str | None:
    artifact_path = Path(path)
    stem = artifact_path.stem.lower().replace("-", "_")
    if stem.startswith("invalid_"):
        stem = stem.removeprefix("invalid_")
    if stem in GENERATOR_SCHEMA_FILES:
        return stem
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    schema_name = payload.get("schema_name")
    if isinstance(schema_name, str) and schema_name in GENERATOR_SCHEMA_FILES:
        return schema_name
    return None


def discover_generator_contract_samples(root: str | Path) -> list[tuple[str, Path]]:
    sample_root = Path(root)
    discovered: list[tuple[str, Path]] = []
    if not sample_root.exists():
        return discovered
    for path in sorted(sample_root.rglob("*.json")):
        schema_name = infer_generator_schema_name(path)
        if schema_name is None:
            continue
        discovered.append((schema_name, path))
    return discovered
