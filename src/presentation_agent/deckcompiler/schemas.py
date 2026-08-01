"""DeckCompiler JSON Schema discovery and Draft 2020-12 registry."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "schemas" / "deckcompiler"
SCHEMA_FILES: dict[str, str] = {
    "artifact_envelope": "artifact-envelope.schema.json",
    "architecture_validation_report": "architecture-validation-report.schema.json",
    "baseline_reachability_report": "baseline-reachability-report.schema.json",
    "bundle_fingerprint_authority": "bundle-fingerprint-authority.schema.json",
    "bundle_fingerprint_cross_clone_report": "bundle-fingerprint-cross-clone-report.schema.json",
    "bundle_fingerprint_history_replay": "bundle-fingerprint-history-replay.schema.json",
    "bundle_fingerprint_policy": "bundle-fingerprint-policy.schema.json",
    "creative_fit_report": "creative-fit-report.schema.json",
    "composite_qa_acceptance": "composite-qa-acceptance.schema.json",
    "composite_qa_report": "composite-qa-report.schema.json",
    "contact_sheet_manifest": "contact-sheet-manifest.schema.json",
    "codex_skillset_execution_plan": "codex-skillset-execution-plan.schema.json",
    "codex_pptx_generation_run": "codex-pptx-generation-run.schema.json",
    "deckcompiler_run_manifest": "deckcompiler-run-manifest.schema.json",
    "design_invariants": "design-invariants.schema.json",
    "evidence_unit": "evidence-unit.schema.json",
    "evidence_unit_registry": "evidence-unit-registry.schema.json",
    "evidence_allocation_report": "evidence-allocation-report.schema.json",
    "external_execution_acceptance": "external-execution-acceptance.schema.json",
    "external_execution_record": "external-execution-record.schema.json",
    "external_execution_request": "external-execution-request.schema.json",
    "external_execution_verification_report": "external-execution-verification-report.schema.json",
    "external_skillset_pin": "external-skillset-pin.schema.json",
    "external_visual_qa_output_contract_audit": "external-visual-qa-output-contract-audit.schema.json",
    "external_visual_qa_reconciliation": "external-visual-qa-reconciliation.schema.json",
    "external_visual_qa_source_results": "external-visual-qa-source-results.schema.json",
    "expected_finding": "expected-finding.schema.json",
    "expected_output_contract": "expected-output-contract.schema.json",
    "failure_detection_report": "failure-detection-report.schema.json",
    "fault_application_record": "fault-application-record.schema.json",
    "fault_injection_spec": "fault-injection-spec.schema.json",
    "fault_run_evidence_capsule_manifest": "fault-run-evidence-capsule-manifest.schema.json",
    "fixture_provenance": "fixture-provenance.schema.json",
    "general_generate_workflow_manifest": "general-generate-workflow-manifest.schema.json",
    "input_request": "input-request.schema.json",
    "git_object_bundle_fingerprint": "git-object-bundle-fingerprint.schema.json",
    "legacy_bundle_fingerprint_correction": "legacy-bundle-fingerprint-correction.schema.json",
    "phase4_design_system": "phase4-design-system.schema.json",
    "phase4_editable_template_spec": "phase4-editable-template-spec.schema.json",
    "phase4_generation_provenance": "phase4-generation-provenance.schema.json",
    "phase4_geometry_fit_report": "phase4-geometry-fit-report.schema.json",
    "phase4_input_provenance": "phase4-input-provenance.schema.json",
    "phase4_pending_visual_target_manifest": "phase4-pending-visual-target-manifest.schema.json",
    "phase4_regeneration_history": "phase4-regeneration-history.schema.json",
    "phase4_semantic_sidecar": "phase4-semantic-sidecar.schema.json",
    "phase4_validation_report": "phase4-validation-report.schema.json",
    "phase4_visual_bundle_acceptance": "phase4-visual-bundle-acceptance.schema.json",
    "phase4_visual_target_manifest": "phase4-visual-target-manifest.schema.json",
    "phase3_evidence_unit_registry": "phase3-evidence-unit-registry.schema.json",
    "phase3_artifact_graph": "phase3-artifact-graph.schema.json",
    "phase3_run_manifest": "phase3-run-manifest.schema.json",
    "phase3_validation_report": "phase3-validation-report.schema.json",
    "module_art_directions": "module-art-directions.schema.json",
    "png_reconstruction_manifest": "png-reconstruction-manifest.schema.json",
    "pngtopptx_handoff_manifest": "pngtopptx-handoff-manifest.schema.json",
    "pngtopptx_invocation_plan": "pngtopptx-invocation-plan.schema.json",
    "pngtopptx_project_asset_manifest": "pngtopptx-project-asset-manifest.schema.json",
    "pngtopptx_project_crop_plan": "pngtopptx-project-crop-plan.schema.json",
    "qa_dimension_report": "qa-dimension-report.schema.json",
    "qa_finding": "qa-finding.schema.json",
    "reconstruction_constraints": "reconstruction-constraints.schema.json",
    "slide_blueprint_collection": "slide-blueprint-collection.schema.json",
    "source_corpus": "source-corpus.schema.json",
    "source_coverage_report": "source-coverage-report.schema.json",
    "source_gap_report": "source-gap-report.schema.json",
    "source_item": "source-item.schema.json",
    "source_locator": "source-locator.schema.json",
    "source_locator_registry": "source-locator-registry.schema.json",
    "platform_image_capability_attestation": "platform-image-capability-attestation.schema.json",
    "platform_image_attempt_seal": "platform-image-attempt-seal.schema.json",
    "platform_image_execution_record": "platform-image-execution-record.schema.json",
    "platform_image_regeneration_history": "platform-image-regeneration-history.schema.json",
    "platform_image_request": "platform-image-request.schema.json",
    "platform_image_verification_report": "platform-image-verification-report.schema.json",
    "platform_image_visual_review": "platform-image-visual-review.schema.json",
    "phase4c_canary_report": "phase4c-canary-report.schema.json",
    "repair_contract": "repair-contract.schema.json",
    "repair_plan": "repair-plan.schema.json",
    "invalidation_manifest": "invalidation-manifest.schema.json",
    "repair_history": "repair-history.schema.json",
    "before_after_manifest": "before-after-manifest.schema.json",
    "unified_release_gate_report": "unified-release-gate-report.schema.json",
    "phase6_acceptance": "phase6-acceptance.schema.json",
    "visual_target_manifest": "visual-target-manifest.schema.json",
    "visual_dna": "visual-dna.schema.json",
    "workflow_resolution": "workflow-resolution.schema.json",
    "release_contract": "release-contract.schema.json",
    "runtime_environment_manifest": "runtime-environment-manifest.schema.json",
    "runtime_bundle_compatibility": "runtime-bundle-compatibility.schema.json",
    "external_prerequisite_manifest": "external-prerequisite-manifest.schema.json",
    "component_provenance_manifest": "component-provenance-manifest.schema.json",
    "build_week_provenance": "build-week-provenance.schema.json",
    "demo_run_manifest": "demo-run-manifest.schema.json",
    "semantic_reproducibility_report": "semantic-reproducibility-report.schema.json",
    "delivery_manifest": "delivery-manifest.schema.json",
    "package_inventory": "package-inventory.schema.json",
    "package_validation_report": "package-validation-report.schema.json",
    "release_candidate_gate": "release-candidate-gate.schema.json",
    "fresh_clone_environment_report": "fresh-clone-environment-report.schema.json",
    "fresh_clone_reproduction_report": "fresh-clone-reproduction-report.schema.json",
    "canonical_vs_fresh_comparison_report": "canonical-vs-fresh-comparison-report.schema.json",
    "final_release_gate": "final-release-gate.schema.json",
    "devpost_evidence_index": "devpost-evidence-index.schema.json",
}


@lru_cache(maxsize=None)
def load_schema(schema_name: str) -> dict[str, Any]:
    filename = SCHEMA_FILES.get(schema_name)
    if filename is None:
        raise ValueError(f"unknown DeckCompiler schema: {schema_name}")
    return json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def schema_registry() -> Registry:
    resources: list[tuple[str, Resource[Any]]] = []
    paths = sorted(SCHEMA_DIR.glob("*.schema.json"))
    paths.append(REPO_ROOT / "schemas" / "slide_blueprint.schema.json")
    paths.append(REPO_ROOT / "schemas" / "slide_semantic_sidecar.schema.json")
    paths.extend(sorted((REPO_ROOT / "schemas" / "creative_frontend").glob("*.schema.json")))
    for path in paths:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def validator_for(schema_name: str) -> Draft202012Validator:
    return Draft202012Validator(
        load_schema(schema_name),
        registry=schema_registry(),
        format_checker=FormatChecker(),
    )


__all__ = ["SCHEMA_DIR", "SCHEMA_FILES", "load_schema", "schema_registry", "validator_for"]
