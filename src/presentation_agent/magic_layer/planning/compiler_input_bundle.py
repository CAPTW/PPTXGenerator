from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.presentation_agent.magic_layer.planning.editable_candidate_spec import minimal_editable_candidate_spec


def minimal_compiler_input_bundle() -> dict[str, Any]:
    editable_spec = minimal_editable_candidate_spec()
    return {
        "schema": "compiler_input_bundle.v1",
        "bundle_id": "sample_minimal_cover_hero_bundle",
        "editable_candidate_spec_id": editable_spec["spec_id"],
        "template_id": editable_spec["template_id"],
        "archetype_id": editable_spec["archetype_id"],
        "required_inputs": ["editable_candidate_spec"],
        "editable_candidate_spec": editable_spec,
        "asset_manifest": [{"asset_id": "none", "role": "none", "replaceable": False, "bounded": True, "semantic": False, "allowed_in_pptx": False, "validation_requirements": []}],
        "theme_tokens": editable_spec.get("style_tokens", {}),
        "validation_contract": {"protected_artifact_guard_required": True, "no_canonical_promotion": True},
        "expected_outputs": ["editable_candidate.pptx", "pptx_ooxml_ledger.json", "pptx_semantic_editability_ledger.json", "B03 validation report"],
        "downstream_gates": ["B03_native_validation_gate", "B01_render_review_optional"],
        "forbidden_outputs": ["full_slide_raster", "screenshot_slide", "semantic_raster_fallback", "source_bound_deck", "canonical_artifact_overwrite"],
        "provenance": {"sample_only": True, "generated_for_tests": True, "product_evidence": False},
        "limitations": ["compiler_input_only_not_compiled"],
        "created_pptx": False,
        "product_pass": False,
    }


def build_compiler_input_bundle(editable_candidate_spec: dict[str, Any]) -> dict[str, Any]:
    spec = deepcopy(editable_candidate_spec)
    return {
        "schema": "compiler_input_bundle.v1",
        "bundle_id": f"{spec.get('spec_id', 'editable_spec')}_compiler_bundle",
        "editable_candidate_spec_id": spec.get("spec_id"),
        "template_id": spec.get("template_id"),
        "archetype_id": spec.get("archetype_id"),
        "required_inputs": ["editable_candidate_spec"],
        "editable_candidate_spec": spec,
        "asset_manifest": [],
        "theme_tokens": spec.get("style_tokens", {}),
        "validation_contract": {"protected_artifact_guard_required": True, "no_canonical_promotion": True},
        "expected_outputs": ["editable_candidate.pptx", "pptx_ooxml_ledger.json", "pptx_semantic_editability_ledger.json", "B03 validation report"],
        "downstream_gates": ["B03_native_validation_gate", "B01_render_review_optional"],
        "forbidden_outputs": ["full_slide_raster", "screenshot_slide", "semantic_raster_fallback", "source_bound_deck", "canonical_artifact_overwrite"],
        "provenance": {"source": "T02_compiler_input_bundle_builder", "product_evidence": False},
        "limitations": ["compiler_input_only_not_compiled"],
        "created_pptx": False,
        "product_pass": False,
    }
