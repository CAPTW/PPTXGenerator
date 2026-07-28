"""Runtime stage executors that adapt the legacy workers into the gated harness."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..non_pptx_modules.document_asset_crop import load_document_crop_file
from ..non_pptx_modules.reference_scanner import load_reference_brief_context, scan_reference_pack
from ..non_pptx_modules.runtime_config import RuntimePipelineConfig
from ..non_pptx_modules.runtime_pipeline import (
    RuntimeWorkspace,
    ensure_runtime_dirs,
    trusted_runtime_execution,
)
from ..non_pptx_modules.state_schemas import (
    DEFAULT_STATE_FILENAMES,
    load_state_file,
    normalize_continuity_guidance_and_mirror,
    proof_unit_registry_from_proof_module_manifest,
    save_state_file,
)
from ..non_pptx_modules.shared_proof_registry import (
    LEGACY_PROOF_MODULE_MANIFEST_FINGERPRINT_KEY,
    PROOF_UNIT_REGISTRY_FINGERPRINT_KEY,
    is_legacy_manifest_migration_mode,
    proof_artifact_contract_payload,
    shared_proof_consumer_policy,
)
from ..non_pptx_modules.workflow_contract_matrix import (
    WORKFLOW_FAMILY_CONTRACTS,
    default_workflow_option_provenance,
    evaluate_content_plan_conformance,
    policy_id_for_option,
)
from ..pptx_compiler import BuildManifest, load_pptx_compile_file
from ..qa_compile_policy import summarize_qa_verdict, summarize_render_validation_verdict
from ..reference_confidence import (
    build_reference_approval_basis,
    build_reference_artifact_entry,
    build_reference_design_tokens,
    build_reference_style_tokens,
    summarize_reference_scan_confidence,
)
from ..review_loop_policy import summarize_crop_visual_review
from .invalidation import fingerprint_path, fingerprint_text
from .execution_surface import (
    ActiveExecutionSurface,
    build_aligned_runtime_execution_surface,
    stage_execution_surface,
)
from .gate_policy import DEFAULT_GATE_APPROVAL_POLICY
from .orchestrator import PipelineOrchestrator
from .render_validation import validate_local_pptx
from .state_store import ArtifactEnvelope, FingerprintRecord, SourceEvidence
from .stages import PIPELINE_STAGE_ORDER, PipelineStage, coerce_stage
from .workflow_boundary_registry import WorkflowStageBoundary, stage_boundary, stage_tool_names


REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_SET_PATHS = (
    REPO_ROOT / "prompts" / "implement_harness.md",
    REPO_ROOT / "prompts" / "run_deck_task.md",
)
SCHEMA_DIR = REPO_ROOT / "schemas"
RENDERER_VERSION_PATHS = (
    REPO_ROOT / "src" / "presentation_agent" / "pptx_compiler.py",
    REPO_ROOT / "src" / "presentation_agent" / "pipeline" / "render_validation.py",
)
WORKFLOW_CONTRACT_POLICY_PATHS = (
    REPO_ROOT / "src" / "presentation_agent" / "non_pptx_modules" / "workflow_contract_matrix.py",
)
MASTER_TEMPLATE_BUNDLE_PATH = "master-template-bundle.json"
GATE_POLICY = DEFAULT_GATE_APPROVAL_POLICY


@dataclass(slots=True)
class ExecutorResult:
    artifact: ArtifactEnvelope
    detail: str


@dataclass(slots=True)
class PipelineRuntimeContext:
    config: RuntimePipelineConfig
    workspace: RuntimeWorkspace
    orchestrator: PipelineOrchestrator
    execution_surface: object


class RuntimeStageExecutor:
    """Callable stage adapter with an ACL and stage-boundary check."""

    def __init__(
        self,
        context: PipelineRuntimeContext,
        *,
        stage: PipelineStage,
        boundary: WorkflowStageBoundary,
        execution_surface: ActiveExecutionSurface | None = None,
        handler,
    ) -> None:
        self.context = context
        self.stage = stage
        self.boundary = boundary
        self.execution_surface = execution_surface or stage_execution_surface(stage)
        self.tool_names = stage_tool_names(stage)
        self.capability_ids = boundary.skill_capability_ids
        self.resource_ids = boundary.resource_ids
        self.boundary_tool_ids = boundary.tool_ids
        self.prompt_ids = boundary.prompt_ids
        self.runtime_stage_sequence = self.execution_surface.runtime_stage_sequence
        self._handler = handler

    @property
    def runtime_stage_artifacts(self) -> tuple[Path, ...]:
        return self.execution_surface.expected_runtime_artifacts(self.context.workspace)

    def execute(self, *, current_stage: PipelineStage | str, force: bool = False) -> ExecutorResult:
        normalized_stage = coerce_stage(current_stage)
        if normalized_stage != self.stage:
            raise PermissionError(
                f"executor for {self.stage.value} cannot run during {normalized_stage.value}"
            )
        for tool_name in self.tool_names:
            self.context.orchestrator.ensure_tool_allowed(self.stage, tool_name)
        return self._handler(self.context, force=force)


def build_stage_executors(
    config: RuntimePipelineConfig,
    workspace: RuntimeWorkspace,
    orchestrator: PipelineOrchestrator,
) -> dict[PipelineStage, RuntimeStageExecutor]:
    context = PipelineRuntimeContext(
        config=config,
        workspace=workspace,
        orchestrator=orchestrator,
        execution_surface=build_aligned_runtime_execution_surface(config, workspace),
    )
    ensure_runtime_dirs(workspace)
    return {
        stage: RuntimeStageExecutor(
            context,
            stage=stage,
            boundary=stage_boundary(stage),
            execution_surface=stage_execution_surface(stage),
            handler=_stage_handler(stage),
        )
        for stage in PIPELINE_STAGE_ORDER
    }


def _stage_handler(stage: PipelineStage) -> Any:
    return {
        PipelineStage.INGEST: _execute_ingest,
        PipelineStage.DESIGN_REFERENCE_CHECK: _execute_design_reference_check,
        PipelineStage.MASTER_TEMPLATE: _execute_master_template,
        PipelineStage.CONTENT_PLAN: _execute_content_plan,
        PipelineStage.GENERATE: _execute_generate,
        PipelineStage.QA: _execute_qa,
        PipelineStage.RENDER_LOCAL_PPTX: _execute_render_local_pptx,
    }[stage]


def collect_pipeline_fingerprints(
    config: RuntimePipelineConfig,
    workspace: RuntimeWorkspace,
) -> list[FingerprintRecord]:
    brief_payload = _load_brief_payload(workspace.brief_path)
    request_contract = _normalize_request_contract(config, workspace, brief_payload)
    fingerprint_records: list[FingerprintRecord] = [
        FingerprintRecord(
            key="request_contract",
            digest=fingerprint_text(_canonical_json(request_contract)),
            invalidates_from_stage=PipelineStage.INGEST,
            sources=[_display_path(workspace.brief_path, workspace.base_dir)],
        ),
        FingerprintRecord(
            key="prompt_set_version",
            digest=_fingerprint_inputs(PROMPT_SET_PATHS),
            invalidates_from_stage=PipelineStage.INGEST,
            sources=[_display_path(path, REPO_ROOT) for path in PROMPT_SET_PATHS],
        ),
        FingerprintRecord(
            key="schema_version",
            digest=_fingerprint_inputs(tuple(sorted(SCHEMA_DIR.glob("*.json")))),
            invalidates_from_stage=PipelineStage.INGEST,
            sources=[_display_path(path, REPO_ROOT) for path in sorted(SCHEMA_DIR.glob("*.json"))],
        ),
        FingerprintRecord(
            key="renderer_version",
            digest=_fingerprint_inputs(RENDERER_VERSION_PATHS),
            invalidates_from_stage=PipelineStage.RENDER_LOCAL_PPTX,
            sources=[_display_path(path, REPO_ROOT) for path in RENDERER_VERSION_PATHS],
        ),
        FingerprintRecord(
            key="workflow_contract_policy_version",
            digest=_fingerprint_inputs(WORKFLOW_CONTRACT_POLICY_PATHS),
            invalidates_from_stage=PipelineStage.DESIGN_REFERENCE_CHECK,
            sources=[_display_path(path, REPO_ROOT) for path in WORKFLOW_CONTRACT_POLICY_PATHS],
        ),
    ]

    for asset in _collect_ingest_assets(config, workspace, brief_payload):
        if "content_source" in asset["roles"]:
            invalidation_stage = PipelineStage.CONTENT_PLAN
        elif "design_reference" in asset["roles"] or "brand_constraint" in asset["roles"]:
            invalidation_stage = PipelineStage.DESIGN_REFERENCE_CHECK
        else:
            continue
        fingerprint_records.append(
            FingerprintRecord(
                key=f"{asset['roles'][0]}::{asset['asset_id']}",
                digest=str(asset["fingerprint"]),
                invalidates_from_stage=invalidation_stage,
                sources=[str(asset["filename"])],
            )
        )
    master_template_bundle_path = workspace.state_dir / MASTER_TEMPLATE_BUNDLE_PATH
    if master_template_bundle_path.is_file():
        fingerprint_records.append(
            FingerprintRecord(
                key="master_template_bundle",
                digest=fingerprint_path(master_template_bundle_path),
                invalidates_from_stage=PipelineStage.CONTENT_PLAN,
                sources=[_display_path(master_template_bundle_path, workspace.base_dir)],
            )
        )
    proof_module_manifest_path = workspace.state_path("proof_module_manifest")
    proof_unit_registry_path = workspace.state_path("proof_unit_registry")
    workflow_plan_path = workspace.state_path("workflow_plan")
    workflow_option = None
    if workflow_plan_path.is_file():
        workflow_plan = load_state_file(workflow_plan_path)
        workflow_option = str(getattr(workflow_plan, "workflow_option", "") or "")
    if shared_proof_consumer_policy(workflow_option) is not None and (
        proof_unit_registry_path.is_file() or proof_module_manifest_path.is_file()
    ):
        proof_structure_digest, proof_structure_sources = _proof_structure_fingerprint_payload(workspace)
        fingerprint_records.append(
            FingerprintRecord(
                key=PROOF_UNIT_REGISTRY_FINGERPRINT_KEY,
                digest=proof_structure_digest,
                invalidates_from_stage=PipelineStage.CONTENT_PLAN,
                sources=proof_structure_sources,
            )
        )
    return fingerprint_records


def _content_plan_blocked_result(
    context: PipelineRuntimeContext,
    workflow_plan,
    *,
    provenance: dict[str, object],
    failure_reasons: list[str],
    failure_codes: list[str] | None = None,
    accepted_checks: list[str] | None = None,
    accepted_basis: list[str] | None = None,
    conformance: dict[str, object] | None = None,
    outputs: list[str] | None = None,
    proof_unit_registry_path: str | None = None,
    proof_unit_registry_summary: dict[str, object] | None = None,
    proof_module_manifest_path: str | None = None,
    proof_module_manifest_summary: dict[str, object] | None = None,
    proof_artifact_contract: dict[str, object] | None = None,
    fingerprints: list[dict[str, object]] | None = None,
) -> ExecutorResult:
    if conformance is None:
        policy_option_id = str(provenance.get("selected_option_id") or getattr(workflow_plan, "workflow_option", "") or "")
        contract = WORKFLOW_FAMILY_CONTRACTS.get(policy_option_id)
        conformance = {
            "status": "fail",
            "requested_option_id": provenance.get("requested_option_id"),
            "selected_option_id": policy_option_id,
            "contract_status": provenance.get("contract_status", "absent"),
            "policy_id": policy_id_for_option(policy_option_id),
            "required_sections": list(contract.required_sections) if contract is not None else [],
            "required_main_story_roles": list(contract.required_main_story_roles) if contract is not None else [],
            "accepted_checks": accepted_checks or [],
            "failure_reasons": failure_reasons,
            "failure_codes": failure_codes or ["requested-workflow-option-incompatible"],
            "accepted_basis": accepted_basis or [str(provenance.get("reason") or "")],
        }
    artifact = ArtifactEnvelope(
        stage=PipelineStage.CONTENT_PLAN,
        status=GATE_POLICY.blocking_status(PipelineStage.CONTENT_PLAN),
        inputs=[_state_file_path(context.workspace, "master_template"), _state_file_path(context.workspace, "workflow_plan")],
        outputs=outputs or [],
        source_evidence=[
            SourceEvidence(artifact=_state_file_path(context.workspace, "master_template"), reason="approved template bundle"),
            SourceEvidence(artifact=_state_file_path(context.workspace, "workflow_plan"), reason="workflow-option contract evaluation"),
        ],
        workflow_option=str(getattr(workflow_plan, "workflow_option", "")),
        requested_workflow_option=provenance.get("requested_option_id"),
        workflow_option_provenance=provenance,
        plan_conformance=conformance,
        failure_reason=" ".join(failure_reasons),
        next_stage=PipelineStage.CONTENT_PLAN.value,
        workflow_plan_path=_state_file_path(context.workspace, "workflow_plan"),
        proof_unit_registry_path=proof_unit_registry_path,
        proof_unit_registry_summary=proof_unit_registry_summary,
        proof_module_manifest_path=proof_module_manifest_path,
        proof_module_manifest_summary=proof_module_manifest_summary,
        proof_artifact_contract=proof_artifact_contract,
        fingerprints=fingerprints or [],
    )
    return ExecutorResult(
        artifact=artifact,
        detail=f"Blocked CONTENT_PLAN: {failure_reasons[0]}",
    )


def _execute_ingest(context: PipelineRuntimeContext, *, force: bool) -> ExecutorResult:
    del force
    brief_payload = _load_brief_payload(context.workspace.brief_path)
    assets = _collect_ingest_assets(context.config, context.workspace, brief_payload)
    fingerprints = collect_pipeline_fingerprints(context.config, context.workspace)
    evidence = [
        SourceEvidence(asset_id=str(asset["asset_id"]), reason="classified runtime input")
        for asset in assets
    ] or [
        SourceEvidence(artifact=_display_path(context.workspace.brief_path, context.workspace.base_dir), reason="loaded brief")
    ]
    artifact = ArtifactEnvelope(
        stage=PipelineStage.INGEST,
        status=GATE_POLICY.success_status(PipelineStage.INGEST),
        inputs=[_display_path(context.workspace.brief_path, context.workspace.base_dir)],
        outputs=[_state_file_path(context.workspace, "intake_manifest")],
        source_evidence=evidence,
        assets=assets,
        request_contract=_normalize_request_contract(context.config, context.workspace, brief_payload),
        fingerprints=[record.model_dump(mode="json") for record in fingerprints],
    )
    detail = f"Classified {len(assets)} runtime inputs and refreshed {len(fingerprints)} pipeline fingerprints."
    return ExecutorResult(artifact=artifact, detail=detail)


def _execute_design_reference_check(context: PipelineRuntimeContext, *, force: bool) -> ExecutorResult:
    with trusted_runtime_execution("stage-gated-harness:DESIGN_REFERENCE_CHECK"):
        workflow_result = context.execution_surface.execute_single(PipelineStage.DESIGN_REFERENCE_CHECK, force=force)
    workflow_plan = load_state_file(context.workspace.state_path("workflow_plan"))
    reference_dna_path: Path | None = None
    reference_dna = None
    reference_scan_confidence = summarize_reference_scan_confidence(None)
    references: list[dict[str, object]] = []
    brand_constraints: list[dict[str, object]] = []
    design_tokens: dict[str, object] = {
        "workflow": getattr(workflow_plan, "approved_workflow", None) or getattr(workflow_plan, "workflow_option", None),
    }
    written = [*_as_display_paths(workflow_result.written, context.workspace.base_dir)]

    if context.workspace.reference_pack_path is not None:
        brief_context = load_reference_brief_context(context.workspace.brief_path)
        reference_dna = scan_reference_pack(
            context.workspace.reference_pack_path,
            workflow_plan=workflow_plan,
            deck_title=getattr(workflow_plan, "deck_title", None),
            brief_context=brief_context,
        )
        reference_scan_confidence = summarize_reference_scan_confidence(reference_dna)
        reference_dna_path = context.workspace.state_path("reference_dna")
        save_state_file(reference_dna, reference_dna_path)
        written.append(_display_path(reference_dna_path, context.workspace.base_dir))
        references.append(build_reference_artifact_entry(reference_dna, reference_scan_confidence))

    design_tokens.update(build_reference_design_tokens(reference_dna, reference_scan_confidence))

    if context.workspace.brand_inputs_path is not None:
        brand_summary = _load_structured_document(context.workspace.brand_inputs_path)
        brand_constraints.append(
            {
                "asset_id": "brand_inputs",
                "role": "brand_constraint",
                "confidence": 1.0,
            }
        )
        design_tokens["brand_inputs"] = _summarize_mapping(brand_summary)

    artifact = ArtifactEnvelope(
        stage=PipelineStage.DESIGN_REFERENCE_CHECK,
        status=GATE_POLICY.success_status(PipelineStage.DESIGN_REFERENCE_CHECK),
        inputs=[_state_file_path(context.workspace, "intake_manifest")],
        outputs=[_state_file_path(context.workspace, "design_reference_report"), *written],
        source_evidence=[
            SourceEvidence(artifact=_state_file_path(context.workspace, "workflow_plan"), reason="workflow plan established the design route")
        ],
        references=references,
        brand_constraints=brand_constraints,
        design_tokens=design_tokens,
        workflow_plan_path=_state_file_path(context.workspace, "workflow_plan"),
        reference_dna_path=_display_path(reference_dna_path, context.workspace.base_dir) if reference_dna_path is not None else None,
        design_reference_mode="user_reference_pack" if context.workspace.reference_pack_path is not None else "local_default",
        reference_scan_confidence=reference_scan_confidence.model_dump(mode="json"),
        reference_scan_warnings=list(reference_scan_confidence.warnings),
    )
    detail = "Planned the workflow and froze the design-reference basis for downstream template approval."
    return ExecutorResult(artifact=artifact, detail=detail)


def _execute_master_template(context: PipelineRuntimeContext, *, force: bool) -> ExecutorResult:
    del force
    state = context.orchestrator.load_state()
    attempt = 1 + sum(1 for entry in state.history if entry.stage == PipelineStage.MASTER_TEMPLATE)
    design_artifact = context.orchestrator.store.load_artifact(PipelineStage.DESIGN_REFERENCE_CHECK)
    reference_dna = _maybe_load_state(context.workspace, "reference_dna")
    reference_scan_confidence = summarize_reference_scan_confidence(reference_dna)
    bundle_path = context.workspace.state_dir / MASTER_TEMPLATE_BUNDLE_PATH

    references = []
    if design_artifact is not None:
        raw_references = (design_artifact.model_extra or {}).get("references", [])
        if isinstance(raw_references, list):
            references = [item for item in raw_references if isinstance(item, dict)]
    source_reference_ids = [
        str(reference["asset_id"])
        for reference in references
        if isinstance(reference.get("asset_id"), str) and str(reference["asset_id"]).strip()
    ]
    if context.workspace.brand_inputs_path is not None:
        source_reference_ids.append("brand_inputs")
    style_tokens = _derive_style_tokens(reference_dna, context.workspace, reference_scan_confidence)
    approval_basis = _derive_approval_basis(reference_dna, context.workspace, reference_scan_confidence)
    bundle_payload = {
        "schema_name": "master_template_bundle",
        "schema_version": "1.0",
        "deck_title": getattr(reference_dna, "deck_title", None) or _deck_title_from_brief(context.workspace.brief_path),
        "style_tokens": style_tokens,
        "source_reference_ids": source_reference_ids,
        "approval_basis": approval_basis,
        "reference_scan_confidence": reference_scan_confidence.model_dump(mode="json"),
        "created_from_stage_attempt": attempt,
        "workflow_plan_path": _state_file_path(context.workspace, "workflow_plan"),
        "reference_dna_path": _state_file_path(context.workspace, "reference_dna")
        if context.workspace.state_path("reference_dna").is_file()
        else None,
        "brand_inputs_path": _display_path(context.workspace.brand_inputs_path, context.workspace.base_dir)
        if context.workspace.brand_inputs_path is not None
        else None,
    }
    bundle_path.write_text(json.dumps(bundle_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    bundle_fingerprint = FingerprintRecord(
        key="master_template_bundle",
        digest=fingerprint_path(bundle_path),
        invalidates_from_stage=PipelineStage.CONTENT_PLAN,
        sources=[_display_path(bundle_path, context.workspace.base_dir)],
    )
    artifact = ArtifactEnvelope(
        stage=PipelineStage.MASTER_TEMPLATE,
        status=GATE_POLICY.success_status(PipelineStage.MASTER_TEMPLATE),
        inputs=[_state_file_path(context.workspace, "design_reference_report")],
        outputs=[_state_file_path(context.workspace, "master_template"), _display_path(bundle_path, context.workspace.base_dir)],
        source_evidence=[
            SourceEvidence(artifact=_state_file_path(context.workspace, "design_reference_report"), reason="approved design-reference report"),
        ],
        template_bundle_path=_display_path(bundle_path, context.workspace.base_dir),
        style_tokens=style_tokens,
        source_reference_ids=source_reference_ids,
        approval_basis=approval_basis,
        reference_scan_confidence=reference_scan_confidence.model_dump(mode="json"),
        created_from_stage_attempt=attempt,
        fingerprints=[bundle_fingerprint.model_dump(mode="json")],
    )
    detail = "Created the approved master-template bundle that downstream content planning must consume."
    return ExecutorResult(artifact=artifact, detail=detail)


def _execute_content_plan(context: PipelineRuntimeContext, *, force: bool) -> ExecutorResult:
    workflow_plan = load_state_file(context.workspace.state_path("workflow_plan"))
    typed_provenance = getattr(workflow_plan, "workflow_option_provenance", None)
    if typed_provenance is None:
        selected_option_id = str(getattr(workflow_plan, "workflow_option", "")).strip()
        typed_provenance = default_workflow_option_provenance(
            selected_option_id,
            available_option_ids=[selected_option_id] if selected_option_id else [],
        )
    provenance = typed_provenance.model_dump(mode="json")
    if provenance.get("contract_status") == "incompatible":
        return _content_plan_blocked_result(
            context,
            workflow_plan,
            provenance=provenance,
            failure_reasons=[
                str(provenance.get("reason") or "requested_workflow_option is incompatible with the current brief.")
            ],
            failure_codes=["requested-workflow-option-incompatible"],
            accepted_basis=[str(provenance.get("reason") or "")],
        )

    with trusted_runtime_execution("stage-gated-harness:CONTENT_PLAN"):
        stage_result = context.execution_surface.execute_single(PipelineStage.CONTENT_PLAN, force=force)
    blueprint = load_state_file(context.workspace.state_path("blueprint"))
    selected_workflow_option = str(getattr(blueprint, "chosen_workflow", ""))
    shared_proof_policy = shared_proof_consumer_policy(selected_workflow_option)
    proof_unit_registry = (
        _maybe_load_state(context.workspace, "proof_unit_registry")
        if shared_proof_policy is not None
        else None
    )
    proof_module_manifest = (
        _maybe_load_state(context.workspace, "proof_module_manifest")
        if shared_proof_policy is not None
        and is_legacy_manifest_migration_mode(selected_workflow_option)
        else None
    )
    proof_artifact_migration_status = "not-applicable"
    if shared_proof_policy is not None:
        if proof_unit_registry is not None:
            proof_artifact_migration_status = (
                "legacy-sidecar-ignored" if proof_module_manifest is not None else "native-registry"
            )
        elif proof_module_manifest is not None and is_legacy_manifest_migration_mode(selected_workflow_option):
            proof_artifact_migration_status = "legacy-manifest-upgraded"
    if proof_unit_registry is None and proof_module_manifest is not None and is_legacy_manifest_migration_mode(selected_workflow_option):
        proof_unit_registry = proof_unit_registry_from_proof_module_manifest(proof_module_manifest)
    proof_unit_registry_path = (
        _state_file_path(context.workspace, "proof_unit_registry")
        if context.workspace.state_path("proof_unit_registry").is_file()
        else None
    )
    proof_unit_registry_summary = _proof_unit_registry_summary(proof_unit_registry)
    proof_module_manifest_path = (
        _state_file_path(context.workspace, "proof_module_manifest")
        if context.workspace.state_path("proof_module_manifest").is_file()
        else None
    )
    proof_module_manifest_summary = _proof_module_manifest_summary(proof_module_manifest)
    proof_artifact_contract = _proof_artifact_contract_payload(
        selected_workflow_option,
        proof_unit_registry_path=proof_unit_registry_path,
        proof_module_manifest_path=proof_module_manifest_path,
        migration_status=proof_artifact_migration_status,
    )
    content_plan_fingerprints = []
    if proof_unit_registry_path is not None or proof_module_manifest_path is not None:
        content_plan_fingerprints.append(
            _proof_structure_fingerprint_record(
                context.workspace,
                proof_unit_registry_path=proof_unit_registry_path,
                proof_module_manifest_path=proof_module_manifest_path,
            ).model_dump(mode="json")
        )
    presentation_brief = _maybe_load_state(context.workspace, "presentation_brief")
    slide_function_outline = _maybe_load_state(context.workspace, "slide_function_outline")
    presentation_brief_path = (
        _state_file_path(context.workspace, "presentation_brief")
        if context.workspace.state_path("presentation_brief").is_file()
        else None
    )
    slide_function_outline_path = (
        _state_file_path(context.workspace, "slide_function_outline")
        if context.workspace.state_path("slide_function_outline").is_file()
        else None
    )
    conformance = evaluate_content_plan_conformance(
        workflow_plan,
        blueprint,
        proof_module_manifest=proof_module_manifest,
        proof_unit_registry=proof_unit_registry,
    )
    blueprint = blueprint.model_copy(
        update={
            "workflow_option_provenance": typed_provenance,
            "content_plan_conformance": conformance,
        }
    )
    save_state_file(blueprint, context.workspace.state_path("blueprint"))
    conformance_payload = conformance.model_dump(mode="json")
    accepted_checks = list(conformance.accepted_checks)
    failure_reasons = list(conformance.failure_reasons)
    accepted_basis = list(conformance.accepted_basis)
    if failure_reasons:
        return _content_plan_blocked_result(
            context,
            workflow_plan,
            provenance=provenance,
            failure_reasons=failure_reasons,
            failure_codes=list(conformance.failure_codes),
            accepted_checks=accepted_checks,
            accepted_basis=accepted_basis,
            conformance=conformance_payload,
            proof_unit_registry_path=proof_unit_registry_path,
            proof_unit_registry_summary=proof_unit_registry_summary,
            outputs=[*_as_display_paths(stage_result.written, context.workspace.base_dir)],
            proof_module_manifest_path=proof_module_manifest_path,
            proof_module_manifest_summary=proof_module_manifest_summary,
            proof_artifact_contract=proof_artifact_contract,
            fingerprints=content_plan_fingerprints,
        )
    artifact = ArtifactEnvelope(
        stage=PipelineStage.CONTENT_PLAN,
        status=GATE_POLICY.success_status(PipelineStage.CONTENT_PLAN),
        inputs=[_state_file_path(context.workspace, "master_template"), _state_file_path(context.workspace, "workflow_plan")],
        outputs=[_state_file_path(context.workspace, "content_plan"), *_as_display_paths(stage_result.written, context.workspace.base_dir)],
        source_evidence=[
            SourceEvidence(artifact=_state_file_path(context.workspace, "master_template"), reason="approved template bundle"),
            SourceEvidence(artifact=_state_file_path(context.workspace, "workflow_plan"), reason="workflow-option contract was honored before Gate 2 approval"),
            *(
                [
                    SourceEvidence(
                        artifact=proof_unit_registry_path,
                        reason=f"shared proof-unit registry for `{selected_workflow_option}` content-plan approval",
                    )
                ]
                if proof_unit_registry_path is not None
                else []
            ),
        ],
        blueprint_path=_state_file_path(context.workspace, "blueprint"),
        design_system_path=_state_file_path(context.workspace, "design_system"),
        deck_constitution_path=_state_file_path(context.workspace, "deck_constitution"),
        layout_library_path=_state_file_path(context.workspace, "layout_library"),
        slide_ledger_path=_state_file_path(context.workspace, "slide_ledger"),
        batch_manifest_path=_state_file_path(context.workspace, "batch_manifest")
        if context.workspace.state_path("batch_manifest").is_file()
        else None,
        state_capsule_path=_state_file_path(context.workspace, "state_capsule")
        if context.workspace.state_path("state_capsule").is_file()
        else None,
        workflow_plan_path=_state_file_path(context.workspace, "workflow_plan"),
        presentation_brief_path=presentation_brief_path,
        presentation_brief_summary=(
            {
                "archetype": presentation_brief.archetype.value,
                "tone": presentation_brief.tone,
                "target_deck_length": f"{presentation_brief.target_deck_length.start}-{presentation_brief.target_deck_length.end}",
                "brand_mode": presentation_brief.brand_mode.value,
            }
            if presentation_brief is not None
            else None
        ),
        slide_function_outline_path=slide_function_outline_path,
        slide_function_outline_summary=(
            [
                {
                    "slide_number": item.slide_number,
                    "slide_function": item.slide_function.value,
                    "section": item.section,
                }
                for item in getattr(slide_function_outline, "slides", [])[:10]
            ]
            if slide_function_outline is not None
            else None
        ),
        workflow_option=str(getattr(blueprint, "chosen_workflow", "")),
        requested_workflow_option=provenance.get("requested_option_id"),
        workflow_option_provenance=provenance,
        plan_conformance=conformance_payload,
        proof_unit_registry_path=proof_unit_registry_path,
        proof_unit_registry_summary=proof_unit_registry_summary,
        proof_artifact_contract=proof_artifact_contract,
        fingerprints=content_plan_fingerprints,
        slide_count=len(getattr(blueprint, "slides", [])),
        slides=[
            {
                "slide_number": slide.slide_number,
                "title": slide.title,
                "layout_pattern_id": slide.layout_pattern_id,
            }
            for slide in getattr(blueprint, "slides", [])[:10]
        ],
    )
    detail = "Generated the approved blueprint, visual system, constitution, layout library, and ledger state under the locked workflow contract."
    return ExecutorResult(artifact=artifact, detail=detail)


def _execute_generate(context: PipelineRuntimeContext, *, force: bool) -> ExecutorResult:
    with trusted_runtime_execution("stage-gated-harness:GENERATE"):
        derive_result, extract_result, review_result, render_result = context.execution_surface.execute(
            PipelineStage.GENERATE,
            force=force,
        )
    asset_manifest = load_state_file(context.workspace.state_path("asset_manifest"))
    viz_manifest = load_state_file(context.workspace.state_path("viz_manifest"))
    crop_review_inputs = _maybe_load_document_crop_artifact(context.workspace.asset_dir / "crop-review-inputs.json")
    crop_review_decisions = _maybe_load_document_crop_artifact(context.workspace.asset_dir / "crop-review-decisions.json")
    selected_crops = _maybe_load_document_crop_artifact(context.workspace.asset_dir / "selected-crops.json")
    review_loop_report = summarize_crop_visual_review(
        asset_manifest=asset_manifest,
        viz_manifest=viz_manifest,
        crop_review_inputs=crop_review_inputs,
        crop_review_decisions=crop_review_decisions,
        selected_crops=selected_crops,
    )
    artifact = ArtifactEnvelope(
        stage=PipelineStage.GENERATE,
        status=GATE_POLICY.success_status(PipelineStage.GENERATE),
        inputs=[_state_file_path(context.workspace, "content_plan")],
        outputs=[
            _state_file_path(context.workspace, "generation_manifest"),
            *_as_display_paths(derive_result.written, context.workspace.base_dir),
            *_as_display_paths(extract_result.written, context.workspace.base_dir),
            *_as_display_paths(review_result.written, context.workspace.base_dir),
            *_as_display_paths(render_result.written, context.workspace.base_dir),
        ],
        source_evidence=[
            SourceEvidence(artifact=_state_file_path(context.workspace, "blueprint"), reason="approved content plan"),
        ],
        asset_requests_path=_state_file_path(context.workspace, "asset_requests"),
        asset_manifest_path=_state_file_path(context.workspace, "asset_manifest"),
        viz_spec_path=_state_file_path(context.workspace, "viz_spec"),
        viz_manifest_path=_state_file_path(context.workspace, "viz_manifest"),
        slide_ledger_path=_state_file_path(context.workspace, "slide_ledger"),
        asset_count=len(getattr(asset_manifest, "assets", [])),
        visual_count=len(getattr(viz_manifest, "visuals", [])),
        approval_outcome=review_loop_report.approval_outcome,
        compile_warning_codes=list(review_loop_report.compile_warning_codes),
        pending_review_asset_count=review_loop_report.pending_review_asset_count,
        rejected_asset_count=review_loop_report.rejected_asset_count,
        compile_ready_asset_count=review_loop_report.compile_ready_asset_count,
        review_loop_report=review_loop_report.model_dump(mode="json"),
    )
    detail = "Derived asset requests, rendered crops, reviewed selections, and produced structured visuals."
    return ExecutorResult(artifact=artifact, detail=detail)


def _executor_continuity_policy_inputs(
    state_capsule: Any | None,
    *,
    existing_verdict_matches_qa_status: bool,
) -> tuple[list[Any] | None, list[str] | None]:
    if state_capsule is None:
        return None, None

    continuity_alerts = list(getattr(state_capsule, "continuity_alerts", []) or [])
    if continuity_alerts:
        return continuity_alerts, None

    if existing_verdict_matches_qa_status:
        return None, None

    # Keep the executor fallback behind structured continuity surfaces first.
    continuity_guidance_lines, _structured_mirror = normalize_continuity_guidance_and_mirror(
        continuity_guidance=getattr(state_capsule, "continuity_guidance", None),
        continuity_warnings=None,
    )
    if continuity_guidance_lines:
        return None, continuity_guidance_lines

    # Raw warning strings remain only as a last-resort compatibility fallback.
    legacy_warning_lines, _legacy_mirror = normalize_continuity_guidance_and_mirror(
        continuity_guidance=None,
        continuity_warnings=getattr(state_capsule, "continuity_warnings", None),
    )
    return None, legacy_warning_lines or None


def _execute_qa(context: PipelineRuntimeContext, *, force: bool) -> ExecutorResult:
    with trusted_runtime_execution("stage-gated-harness:QA"):
        compile_result, qa_result, orchestration_result = context.execution_surface.execute(
            PipelineStage.QA,
            force=force,
        )
    qa_report = load_state_file(context.workspace.state_path("qa_report"))
    build_manifest = _load_build_manifest(context.workspace.deck_build_dir / "build-manifest.json")
    generate_artifact = context.orchestrator.store.load_artifact(PipelineStage.GENERATE)
    generate_extras = generate_artifact.model_extra or {} if generate_artifact is not None else {}
    state_capsule = _maybe_load_state(context.workspace, "state_capsule")
    existing_verdict = getattr(qa_report, "verdict_summary", None)
    existing_verdict_matches_qa_status = (
        existing_verdict is not None and getattr(existing_verdict, "qa_status", None) == qa_report.qa_status
    )
    continuity_alerts, continuity_guidance_lines = _executor_continuity_policy_inputs(
        state_capsule,
        existing_verdict_matches_qa_status=existing_verdict_matches_qa_status,
    )
    render_check_failure_codes: list[str] = []
    render_checks_present = False
    if existing_verdict is not None:
        render_checks_present = bool(existing_verdict.render_checks_present)
        for rule in existing_verdict.rule_results:
            if rule.rule_id != "compiled-deck-render-checks":
                continue
            if rule.outcome.value == "blocked":
                render_check_failure_codes.extend(rule.reason_codes)
            break
    qa_verdict_summary = summarize_qa_verdict(
        qa_report=qa_report,
        build_manifest=build_manifest,
        render_checks_present=render_checks_present,
        render_check_failure_codes=render_check_failure_codes,
        continuity_alerts=continuity_alerts or None,
        continuity_guidance_lines=continuity_guidance_lines,
        existing_verdict_summary=existing_verdict,
        approval_outcome=generate_extras.get("approval_outcome") if isinstance(generate_extras.get("approval_outcome"), str) else None,
        review_loop_report=generate_extras.get("review_loop_report"),
    )
    qa_status_value = str(getattr(qa_report, "qa_status", "")).lower()
    qa_outcome = GATE_POLICY.qa_executor_outcome(qa_status_value)
    summary = getattr(qa_report, "summary", None)
    summary_dump = summary.model_dump(mode="json") if summary is not None else {}
    artifact = ArtifactEnvelope(
        stage=PipelineStage.QA,
        status=qa_outcome.status,
        inputs=[_state_file_path(context.workspace, "generation_manifest")],
        outputs=[
            _state_file_path(context.workspace, "qa_report"),
            *_as_display_paths(compile_result.written, context.workspace.base_dir),
            *_as_display_paths(qa_result.written, context.workspace.base_dir),
            *_as_display_paths(orchestration_result.written, context.workspace.base_dir),
        ],
        source_evidence=[
            SourceEvidence(artifact=_state_file_path(context.workspace, "generation_manifest"), reason="generated deck inputs"),
            SourceEvidence(artifact=_display_path(context.workspace.deck_build_dir / "build-manifest.json", context.workspace.base_dir), reason="preflight-rendered deck"),
        ],
        issues=[finding.model_dump(mode="json") for finding in getattr(qa_report, "findings", [])],
        repair_actions=list(getattr(qa_report, "recommended_actions", [])),
        next_stage=qa_outcome.next_stage.value if qa_outcome.next_stage is not None else None,
        raw_qa_status=qa_status_value,
        qa_summary=summary_dump,
        qa_verdict_summary=qa_verdict_summary.model_dump(mode="json"),
        compile_eligibility=qa_verdict_summary.compile_eligibility.value,
        compatibility_warning_codes=list(qa_verdict_summary.compatibility_warning_codes),
        build_manifest_path=_display_path(context.workspace.deck_build_dir / "build-manifest.json", context.workspace.base_dir),
        slide_build_linkage_path=_display_path(context.workspace.deck_build_dir / "slide-build-linkage.json", context.workspace.base_dir),
        slide_count=build_manifest.slide_count,
        warning_count=len(build_manifest.warnings),
        blocking_count=summary_dump.get("blocking_count"),
    )
    detail = "Ran preflight compilation, deterministic deck QA, and continuity orchestration under the QA gate."
    return ExecutorResult(artifact=artifact, detail=detail)


def _execute_render_local_pptx(context: PipelineRuntimeContext, *, force: bool) -> ExecutorResult:
    build_manifest_path = context.workspace.deck_build_dir / "build-manifest.json"
    if force or not build_manifest_path.is_file():
        with trusted_runtime_execution("stage-gated-harness:RENDER_LOCAL_PPTX"):
            context.execution_surface.execute_single(PipelineStage.RENDER_LOCAL_PPTX, force=True)
    build_manifest = _load_build_manifest(build_manifest_path)
    slide_build_linkage_path = context.workspace.deck_build_dir / "slide-build-linkage.json"
    pptx_path = _resolve_output_path(build_manifest.pptx_path, context.workspace.base_dir)
    try:
        render_validation = validate_local_pptx(pptx_path)
        failure_reason = None
    except (FileNotFoundError, ValueError) as exc:
        render_validation = {
            "file_size_bytes": pptx_path.stat().st_size if pptx_path.is_file() else 0,
            "zip_readable": False,
            "presentation_xml_present": False,
            "slide_count": 0,
            "checksum": None,
        }
        failure_reason = str(exc)
    qa_artifact = context.orchestrator.store.load_artifact(PipelineStage.QA)
    qa_verdict_summary = None
    if qa_artifact is not None:
        qa_extras = qa_artifact.model_extra or {}
        candidate_summary = qa_extras.get("qa_verdict_summary")
        if isinstance(candidate_summary, dict):
            qa_verdict_summary = candidate_summary
    if qa_verdict_summary is None:
        qa_report = load_state_file(context.workspace.state_path("qa_report"))
        qa_verdict_summary = getattr(qa_report, "verdict_summary", None)
    render_rule_summary = summarize_render_validation_verdict(
        render_validation=render_validation,
        failure_reason=failure_reason,
        qa_verdict_summary=qa_verdict_summary,
        build_manifest=build_manifest,
    )
    render_outcome = GATE_POLICY.render_executor_outcome(failed=failure_reason is not None)
    artifact = ArtifactEnvelope(
        stage=PipelineStage.RENDER_LOCAL_PPTX,
        status=render_outcome.status,
        inputs=[_state_file_path(context.workspace, "qa_report")],
        outputs=[_state_file_path(context.workspace, "render_report"), _display_path(build_manifest_path, context.workspace.base_dir)],
        source_evidence=[
            SourceEvidence(artifact=_state_file_path(context.workspace, "qa_report"), reason="QA gate passed before final render"),
            SourceEvidence(artifact=_display_path(build_manifest_path, context.workspace.base_dir), reason="local build manifest"),
        ],
        pptx_path=str(pptx_path),
        build_manifest_path=_display_path(build_manifest_path, context.workspace.base_dir),
        slide_build_linkage_path=_display_path(slide_build_linkage_path, context.workspace.base_dir),
        render_validation=render_validation,
        render_rule_summary=render_rule_summary.model_dump(mode="json"),
        render_metadata={
            "renderer_version": _fingerprint_inputs(RENDERER_VERSION_PATHS),
            "build_manifest_slide_count": build_manifest.slide_count,
            "compiled_layout_patterns": list(build_manifest.compiled_layout_patterns),
            "warning_count": len(build_manifest.warnings),
        },
        compile_eligibility=render_rule_summary.compile_eligibility.value,
        compatibility_warning_codes=list(render_rule_summary.compatibility_warning_codes),
        failure_reason=failure_reason,
        next_stage=render_outcome.next_stage.value if render_outcome.next_stage is not None else None,
    )
    detail = "Validated the local PPTX output and recorded final render metadata."
    return ExecutorResult(artifact=artifact, detail=detail)


def _collect_ingest_assets(
    config: RuntimePipelineConfig,
    workspace: RuntimeWorkspace,
    brief_payload: dict[str, Any],
) -> list[dict[str, object]]:
    del config
    assets: list[dict[str, object]] = []
    materials = brief_payload.get("current_materials", [])
    if isinstance(materials, list):
        for material in materials:
            if not isinstance(material, dict):
                continue
            raw_path = material.get("path")
            label = str(material.get("label") or raw_path or f"material-{len(assets) + 1}")
            material_path = _resolve_material_path(raw_path, workspace)
            assets.append(
                {
                    "asset_id": _slugify(label),
                    "filename": _display_path(material_path, workspace.base_dir) if material_path is not None else str(raw_path or label),
                    "roles": ["content_source"],
                    "fingerprint": _digest_path_or_text(material_path, _canonical_json(material)),
                }
            )
    if workspace.notes_path is not None and not any(asset["filename"] == _display_path(workspace.notes_path, workspace.base_dir) for asset in assets):
        assets.append(
            {
                "asset_id": "runtime_notes",
                "filename": _display_path(workspace.notes_path, workspace.base_dir),
                "roles": ["content_source"],
                "fingerprint": _digest_path_or_text(workspace.notes_path, workspace.notes_path.read_text(encoding="utf-8")),
            }
        )
    if workspace.reference_pack_path is not None:
        assets.append(
            {
                "asset_id": "reference_pack",
                "filename": _display_path(workspace.reference_pack_path, workspace.base_dir),
                "roles": ["design_reference"],
                "fingerprint": _digest_path_or_text(workspace.reference_pack_path, workspace.reference_pack_path.as_posix()),
            }
        )
    if workspace.brand_inputs_path is not None:
        assets.append(
            {
                "asset_id": "brand_inputs",
                "filename": _display_path(workspace.brand_inputs_path, workspace.base_dir),
                "roles": ["brand_constraint"],
                "fingerprint": _digest_path_or_text(workspace.brand_inputs_path, workspace.brand_inputs_path.as_posix()),
            }
        )
    return assets


def _normalize_request_contract(
    config: RuntimePipelineConfig,
    workspace: RuntimeWorkspace,
    brief_payload: dict[str, Any],
) -> dict[str, object]:
    return {
        "deck_title": brief_payload.get("deck_title"),
        "topic": brief_payload.get("topic"),
        "audience": _as_text_list(brief_payload.get("audience")),
        "purpose": brief_payload.get("purpose"),
        "delivery_mode": brief_payload.get("delivery_mode"),
        "expected_duration_minutes": brief_payload.get("expected_duration_minutes"),
        "expected_scale_hint": brief_payload.get("expected_scale_hint"),
        "requested_workflow_option": brief_payload.get("requested_workflow_option"),
        "constraints": _as_text_list(brief_payload.get("constraints")),
        "facts": _as_text_list(brief_payload.get("facts")),
        "recommendations": _as_text_list(brief_payload.get("recommendations")),
        "brief_path": _display_path(workspace.brief_path, workspace.base_dir),
        "reference_pack_path": _display_path(workspace.reference_pack_path, workspace.base_dir)
        if workspace.reference_pack_path is not None
        else None,
        "brand_inputs_path": _display_path(workspace.brand_inputs_path, workspace.base_dir)
        if workspace.brand_inputs_path is not None
        else None,
        "notes_path": _display_path(workspace.notes_path, workspace.base_dir) if workspace.notes_path is not None else None,
        "slide_ratio": config.slide_ratio,
        "render_dpi": config.render_dpi,
        "crop_review_loop_limit": config.crop_review_loop_limit,
        "max_crop_candidates_per_source": config.max_crop_candidates_per_source,
        "pptx_name": config.pptx_name,
        "provider": config.provider.model_dump(mode="json", exclude_none=True),
    }


def _derive_style_tokens(reference_dna, workspace: RuntimeWorkspace, reference_scan_confidence=None) -> list[str]:
    tokens = build_reference_style_tokens(reference_dna, reference_scan_confidence)
    if workspace.brand_inputs_path is not None and workspace.brand_inputs_path.is_file():
        brand_summary = _load_structured_document(workspace.brand_inputs_path)
        for key, value in list(brand_summary.items())[:5]:
            if isinstance(value, (str, int, float)) and value:
                tokens.append(f"brand:{key}={value}")
    if not tokens:
        tokens.append("workflow:local-default")
    return list(dict.fromkeys(token for token in tokens if token))


def _derive_approval_basis(reference_dna, workspace: RuntimeWorkspace, reference_scan_confidence=None) -> list[str]:
    basis = build_reference_approval_basis(reference_dna, reference_scan_confidence)
    if workspace.brand_inputs_path is not None:
        basis.append("brand inputs were incorporated into the approved template bundle")
    if not basis:
        basis.append("workflow-planned local runtime inputs established the template bundle")
    return list(dict.fromkeys(item for item in basis if item))


def _state_file_path(workspace: RuntimeWorkspace, schema_name: str) -> str:
    filename = DEFAULT_STATE_FILENAMES.get(schema_name)
    if filename is None:
        filename = f"{schema_name.replace('_', '-')}.json"
    return _display_path(workspace.state_dir / filename, workspace.base_dir)


def _display_path(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def _resolve_output_path(path_text: str, root: Path) -> Path:
    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _resolve_material_path(raw_path: object, workspace: RuntimeWorkspace) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    brief_relative = (workspace.brief_path.parent / candidate).resolve()
    if brief_relative.exists():
        return brief_relative
    return (workspace.base_dir / candidate).resolve()


def _load_brief_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(text)
    elif path.suffix.lower() == ".json":
        payload = json.loads(text)
    else:
        return {"raw_text": text}
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        return {"raw_payload": payload}
    return payload


def _load_structured_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(text)
    else:
        payload = json.loads(text)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        return {"value": payload}
    return payload


def _deck_title_from_brief(path: Path) -> str:
    payload = _load_brief_payload(path)
    deck_title = payload.get("deck_title")
    if isinstance(deck_title, str) and deck_title.strip():
        return deck_title.strip()
    topic = payload.get("topic")
    if isinstance(topic, str) and topic.strip():
        return topic.strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


def _maybe_load_state(workspace: RuntimeWorkspace, schema_name: str):
    path = workspace.state_path(schema_name)
    if not path.is_file():
        return None
    return load_state_file(path)


def _maybe_load_document_crop_artifact(path: Path):
    if not path.is_file():
        return None
    return load_document_crop_file(path)


def _load_build_manifest(path: Path) -> BuildManifest:
    manifest = load_pptx_compile_file(path)
    if not isinstance(manifest, BuildManifest):
        raise TypeError(f"expected build_manifest, found {type(manifest).__name__}")
    return manifest


def _fingerprint_inputs(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(_display_path(path, REPO_ROOT).encode("utf-8"))
        digest.update(fingerprint_path(path).encode("utf-8"))
    return digest.hexdigest()


def _digest_path_or_text(path: Path | None, fallback_text: str) -> str:
    if path is not None and path.exists():
        return fingerprint_path(path)
    return fingerprint_text(fallback_text)


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _slugify(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-") or "asset"


def _as_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _as_display_paths(paths: list[Path], root: Path) -> list[str]:
    return [_display_path(path, root) for path in paths]


def _summarize_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)):
            summary[key] = value
        elif isinstance(value, list):
            summary[key] = [item for item in value[:3]]
        elif isinstance(value, dict):
            summary[key] = {nested_key: nested_value for nested_key, nested_value in list(value.items())[:3]}
        if len(summary) >= 5:
            break
    return summary


def _proof_module_manifest_summary(proof_module_manifest) -> dict[str, object] | None:
    if proof_module_manifest is None:
        return None
    modules = list(getattr(proof_module_manifest, "modules", []) or [])
    return {
        "workflow_option": getattr(proof_module_manifest, "workflow_option", None),
        "module_count": getattr(proof_module_manifest, "module_count", len(modules)),
        "module_minimum": getattr(proof_module_manifest, "module_minimum", None),
        "direct_evidence_module_count": getattr(proof_module_manifest, "direct_evidence_module_count", 0),
        "synthesis_module_count": getattr(proof_module_manifest, "synthesis_module_count", 0),
        "core_claim_section_id": getattr(proof_module_manifest, "core_claim_section_id", None),
        "proof_section_id": getattr(proof_module_manifest, "proof_section_id", None),
        "implication_section_id": getattr(proof_module_manifest, "implication_section_id", None),
        "module_ids": [getattr(module, "module_id", None) for module in modules],
        "status_codes": [
            {
                "module_id": getattr(module, "module_id", None),
                "status": getattr(getattr(module, "status", None), "value", getattr(module, "status", None)),
                "reason_codes": list(getattr(module, "status_reason_codes", []) or []),
                "provenance_reason_codes": list(getattr(module, "provenance_reason_codes", []) or []),
            }
            for module in modules
        ],
    }


def _proof_unit_registry_summary(proof_unit_registry) -> dict[str, object] | None:
    if proof_unit_registry is None:
        return None
    units = list(getattr(proof_unit_registry, "units", []) or [])
    return {
        "workflow_option": getattr(proof_unit_registry, "workflow_option", None),
        "registry_policy_id": getattr(proof_unit_registry, "registry_policy_id", None),
        "unit_count": getattr(proof_unit_registry, "unit_count", len(units)),
        "unit_minimum": getattr(proof_unit_registry, "unit_minimum", None),
        "direct_evidence_unit_count": getattr(proof_unit_registry, "direct_evidence_unit_count", 0),
        "synthesis_unit_count": getattr(proof_unit_registry, "synthesis_unit_count", 0),
        "claim_anchor_section_id": getattr(proof_unit_registry, "claim_anchor_section_id", None),
        "proof_section_id": getattr(proof_unit_registry, "proof_section_id", None),
        "synthesis_anchor_section_id": getattr(proof_unit_registry, "synthesis_anchor_section_id", None),
        "unit_ids": [getattr(unit, "unit_id", None) for unit in units],
        "status_codes": [
            {
                "unit_id": getattr(unit, "unit_id", None),
                "status": getattr(getattr(unit, "status", None), "value", getattr(unit, "status", None)),
                "reason_codes": list(getattr(unit, "status_reason_codes", []) or []),
                "provenance_reason_codes": list(getattr(unit, "provenance_reason_codes", []) or []),
            }
            for unit in units
        ],
    }


def _proof_artifact_contract_payload(
    selected_workflow_option: str,
    *,
    proof_unit_registry_path: str | None,
    proof_module_manifest_path: str | None,
    migration_status: str,
    doctor_report_path: str | None = None,
) -> dict[str, object] | None:
    return proof_artifact_contract_payload(
        selected_workflow_option,
        proof_unit_registry_path=proof_unit_registry_path,
        proof_module_manifest_path=proof_module_manifest_path,
        migration_status=migration_status,
        doctor_report_path=doctor_report_path,
    )


def _proof_structure_fingerprint_record(
    workspace: RuntimeWorkspace,
    *,
    proof_unit_registry_path: str | None,
    proof_module_manifest_path: str | None,
) -> FingerprintRecord:
    digest, sources = _proof_structure_fingerprint_payload(workspace)
    return FingerprintRecord(
        key=PROOF_UNIT_REGISTRY_FINGERPRINT_KEY,
        digest=digest,
        invalidates_from_stage=PipelineStage.CONTENT_PLAN,
        sources=sources or [source for source in (proof_unit_registry_path, proof_module_manifest_path) if source],
    )


def _proof_structure_fingerprint_payload(workspace: RuntimeWorkspace) -> tuple[str, list[str]]:
    proof_unit_registry_path = workspace.state_path("proof_unit_registry")
    proof_module_manifest_path = workspace.state_path("proof_module_manifest")
    if proof_unit_registry_path.is_file():
        proof_unit_registry = load_state_file(proof_unit_registry_path)
        return (
            fingerprint_text(_canonical_json(proof_unit_registry.to_payload())),
            [_display_path(proof_unit_registry_path, workspace.base_dir)],
        )
    if proof_module_manifest_path.is_file():
        proof_module_manifest = load_state_file(proof_module_manifest_path)
        proof_unit_registry = proof_unit_registry_from_proof_module_manifest(proof_module_manifest)
        return (
            fingerprint_text(_canonical_json(proof_unit_registry.to_payload())),
            [_display_path(proof_module_manifest_path, workspace.base_dir)],
        )
    return (
        "",
        [],
    )


def _fingerprint_workspace_artifacts(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(_display_path(path, root).encode("utf-8"))
        digest.update(fingerprint_path(path).encode("utf-8"))
    return digest.hexdigest()
