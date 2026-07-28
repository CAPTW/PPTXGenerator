"""Runtime orchestration for local phase-by-phase and end-to-end execution."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .asset_derivation import derive_assets_from_files, write_asset_derivation_outputs
from .approved_apply import apply_approved_fixes_from_files, write_approved_apply_outputs
from .deck_qa import run_deck_qa_from_files
from .document_asset_crop import (
    load_document_crop_file,
    run_document_asset_crop_from_files,
    run_document_crop_review_from_files,
    write_document_crop_outputs,
)
from .gate2_planner import plan_gate2_from_files, write_gate2_outputs
from .large_deck_orchestration import orchestrate_large_deck_from_files, write_large_deck_outputs
from .post_apply_closure import close_approved_fixes_from_files, write_post_apply_closure_outputs
from .provider_runtime import LLMBackendProof
from ..pptx_compiler import compile_pptx_from_files, load_pptx_compile_file, write_pptx_compile_outputs
from ..review_loop_policy import determine_crop_review_transition
from .remediation_execution import apply_bounded_remediation_from_files, write_remediation_execution_outputs
from .reference_scanner import scan_reference_pack
from .runtime_config import RuntimePipelineConfig, load_runtime_config, save_runtime_config
from .shared_proof_registry import shared_proof_consumer_policy
from .ship_readiness import assess_ship_readiness_from_files, write_ship_readiness_outputs
from ..compat.presentation_contracts import AssetKind, AssetStatus, StageStatus
from ..compat.state_io import DEFAULT_STATE_FILENAMES, load_state_file, save_state_file
from .structured_visuals import run_structured_visuals_from_files, write_structured_visual_outputs
from .upstream_fix_authoring import author_upstream_fixes_from_files, write_upstream_fix_outputs
from .workflow_planner import plan_workflow_from_file_with_provider


LEGACY_RUNTIME_STAGE_ORDER = [
    "gate1-plan",
    "gate2-blueprint",
    "derive-assets",
    "extract-assets",
    "review-crops",
    "render-visuals",
    "compile-pptx",
    "qa-deck",
    "orchestrate-large-deck",
    "apply-remediation",
    "author-upstream-fixes",
    "apply-approved-fixes",
    "close-approved-fixes",
    "assess-ship-readiness",
]
PIPELINE_STAGE_ORDER = LEGACY_RUNTIME_STAGE_ORDER

_RUNTIME_EXECUTION_CONTEXT: ContextVar[str | None] = ContextVar("runtime_execution_context", default=None)


@contextmanager
def trusted_runtime_execution(source: str) -> Iterator[None]:
    token = _RUNTIME_EXECUTION_CONTEXT.set(source)
    try:
        yield
    finally:
        _RUNTIME_EXECUTION_CONTEXT.reset(token)


def _require_trusted_execution(function_name: str) -> None:
    source = _RUNTIME_EXECUTION_CONTEXT.get()
    if source is None:
        raise PermissionError(
            f"{function_name} must run through the stage-gated orchestrator or the explicit deprecated legacy runtime CLI."
        )


@dataclass(slots=True)
class RuntimeWorkspace:
    config_path: Path
    base_dir: Path
    brief_path: Path
    reference_pack_path: Path | None
    brand_inputs_path: Path | None
    notes_path: Path | None
    state_dir: Path
    output_root: Path
    gate2_dir: Path
    orchestration_dir: Path
    asset_dir: Path
    visual_dir: Path
    deck_build_dir: Path

    def state_path(self, schema_name: str) -> Path:
        return self.state_dir / DEFAULT_STATE_FILENAMES[schema_name]

    @property
    def llm_backend_proof_path(self) -> Path:
        return self.state_dir / "llm-backend-proof.json"


@dataclass(slots=True)
class StageExecution:
    stage: str
    skipped: bool
    written: list[Path]
    detail: str


def _resolve(base_dir: Path, value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def resolve_runtime_workspace(config: RuntimePipelineConfig, config_path: str | Path) -> RuntimeWorkspace:
    resolved_config_path = Path(config_path).resolve()
    base_dir = resolved_config_path.parent
    brief_path = _resolve(base_dir, config.paths.brief_path)
    if brief_path is None:
        raise ValueError("runtime config requires a brief_path")
    state_dir = _resolve(base_dir, config.paths.state_dir)
    output_root = _resolve(base_dir, config.paths.output_root)
    gate2_dir = _resolve(base_dir, config.paths.gate2_dir)
    orchestration_dir = _resolve(base_dir, config.paths.orchestration_dir)
    asset_dir = _resolve(base_dir, config.paths.asset_dir)
    visual_dir = _resolve(base_dir, config.paths.visual_dir)
    deck_build_dir = _resolve(base_dir, config.paths.deck_build_dir)
    if state_dir is None or output_root is None or gate2_dir is None or orchestration_dir is None or asset_dir is None or visual_dir is None or deck_build_dir is None:
        raise ValueError("runtime config path resolution failed")
    return RuntimeWorkspace(
        config_path=resolved_config_path,
        base_dir=base_dir,
        brief_path=brief_path,
        reference_pack_path=_resolve(base_dir, config.paths.reference_pack_path),
        brand_inputs_path=_resolve(base_dir, config.paths.brand_inputs_path),
        notes_path=_resolve(base_dir, config.paths.notes_path),
        state_dir=state_dir,
        output_root=output_root,
        gate2_dir=gate2_dir,
        orchestration_dir=orchestration_dir,
        asset_dir=asset_dir,
        visual_dir=visual_dir,
        deck_build_dir=deck_build_dir,
    )


def ensure_runtime_dirs(workspace: RuntimeWorkspace) -> list[Path]:
    created: list[Path] = []
    for path in (
        workspace.state_dir,
        workspace.output_root,
        workspace.gate2_dir,
        workspace.orchestration_dir,
        workspace.asset_dir,
        workspace.visual_dir,
        workspace.deck_build_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    return created


def bootstrap_runtime_config(
    config_path: str | Path,
    config: RuntimePipelineConfig,
    *,
    force: bool = False,
) -> StageExecution:
    resolved_config_path = Path(config_path).resolve()
    if resolved_config_path.is_file() and not force:
        loaded = load_runtime_config(resolved_config_path)
        workspace = resolve_runtime_workspace(loaded, resolved_config_path)
        ensure_runtime_dirs(workspace)
        return StageExecution(stage="bootstrap", skipped=True, written=[resolved_config_path], detail="Runtime config already exists.")
    save_runtime_config(config, resolved_config_path)
    workspace = resolve_runtime_workspace(config, resolved_config_path)
    created = ensure_runtime_dirs(workspace)
    return StageExecution(stage="bootstrap", skipped=False, written=[resolved_config_path, *created], detail="Wrote runtime config and ensured runtime directories.")


def _should_skip(required_paths: list[Path], *, force: bool, resume_skip_completed: bool) -> bool:
    return (not force) and resume_skip_completed and required_paths and all(path.exists() for path in required_paths)


def legacy_stage_artifacts(stage: str, workspace: RuntimeWorkspace) -> list[Path]:
    if stage == "gate1-plan":
        return [
            workspace.state_path("workflow_plan"),
            workspace.state_path("presentation_brief"),
            workspace.state_path("canonical_generation_profile"),
            workspace.state_path("slide_function_outline"),
            workspace.llm_backend_proof_path,
        ]
    if stage == "gate2-blueprint":
        artifacts = [
            workspace.state_path("blueprint"),
            workspace.state_path("presentation_brief"),
            workspace.state_path("canonical_generation_profile"),
            workspace.state_path("slide_function_outline"),
            workspace.state_path("design_system"),
            workspace.state_path("deck_constitution"),
            workspace.state_path("layout_library"),
            workspace.state_path("slide_ledger"),
            workspace.state_path("batch_manifest"),
            workspace.state_path("context_lock"),
            workspace.state_path("handoff_packet"),
            workspace.state_path("state_capsule"),
        ]
        workflow_plan_path = workspace.state_path("workflow_plan")
        if workflow_plan_path.is_file():
            workflow_plan = load_state_file(workflow_plan_path)
            workflow_option = str(getattr(workflow_plan, "workflow_option", "")) or None
            if shared_proof_consumer_policy(workflow_option) is not None:
                artifacts.append(workspace.state_path("proof_unit_registry"))
        if workspace.reference_pack_path is not None:
            artifacts.append(workspace.state_path("reference_dna"))
        return artifacts
    if stage == "derive-assets":
        return [workspace.state_path("asset_requests"), workspace.state_path("viz_spec"), workspace.state_path("slide_ledger")]
    if stage == "extract-assets":
        return [
            workspace.state_path("asset_manifest"),
            workspace.asset_dir / "crop-candidates.json",
            workspace.asset_dir / "crop-review-inputs.json",
            workspace.asset_dir / "crop-review-decisions.json",
            workspace.asset_dir / "selected-crops.json",
        ]
    if stage == "review-crops":
        return [
            workspace.asset_dir / "crop-review-inputs.json",
            workspace.asset_dir / "crop-review-decisions.json",
            workspace.asset_dir / "selected-crops.json",
        ]
    if stage == "render-visuals":
        return [
            workspace.state_path("viz_manifest"),
            workspace.state_path("asset_manifest"),
            workspace.visual_dir / "viz-manifest.json",
            workspace.visual_dir / "asset-manifest.json",
            workspace.visual_dir / "slide-ledger.json",
        ]
    if stage == "compile-pptx":
        return [
            workspace.deck_build_dir / "build-manifest.json",
            workspace.deck_build_dir / "slide-build-linkage.json",
            workspace.deck_build_dir / "slide-ledger.json",
            workspace.deck_build_dir / "deck.pptx",
        ]
    if stage == "qa-deck":
        return [
            workspace.state_path("qa_report"),
            workspace.state_path("qa_governance"),
            workspace.state_path("slide_ledger"),
            workspace.deck_build_dir / "slide-build-linkage.json",
        ]
    if stage == "orchestrate-large-deck":
        return [
            workspace.state_path("batch_manifest"),
            workspace.state_path("context_lock"),
            workspace.state_path("handoff_packet"),
            workspace.state_path("state_capsule"),
            workspace.state_path("remediation_plan"),
            workspace.state_path("slide_ledger"),
            workspace.deck_build_dir / "slide-build-linkage.json",
        ]
    if stage == "apply-remediation":
        return [workspace.state_path("remediation_execution_report")]
    if stage == "author-upstream-fixes":
        return [
            workspace.state_path("upstream_fix_plan"),
            workspace.state_path("approval_packet"),
            workspace.state_path("authoring_deltas"),
            workspace.state_path("state_capsule"),
            workspace.state_path("handoff_packet"),
        ]
    if stage == "apply-approved-fixes":
        return [
            workspace.state_path("approved_apply_report"),
            workspace.state_path("upstream_fix_plan"),
            workspace.state_path("approval_packet"),
            workspace.state_path("authoring_deltas"),
            workspace.state_path("state_capsule"),
            workspace.state_path("handoff_packet"),
        ]
    if stage == "close-approved-fixes":
        return [
            workspace.state_path("closure_report"),
            workspace.state_path("remaining_backlog"),
            workspace.state_path("upstream_fix_plan"),
            workspace.state_path("approval_packet"),
            workspace.state_path("authoring_deltas"),
            workspace.state_path("state_capsule"),
            workspace.state_path("handoff_packet"),
        ]
    if stage == "assess-ship-readiness":
        return [
            workspace.state_path("ship_readiness_report"),
            workspace.state_path("cycle_reset_plan"),
            workspace.state_path("state_capsule"),
            workspace.state_path("handoff_packet"),
        ]
    raise KeyError(f"unknown stage {stage!r}")


def run_gate1_plan(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> StageExecution:
    _require_trusted_execution("run_gate1_plan")
    target = workspace.state_path("workflow_plan")
    presentation_brief_target = workspace.state_path("presentation_brief")
    canonical_generation_profile_target = workspace.state_path("canonical_generation_profile")
    slide_function_outline_target = workspace.state_path("slide_function_outline")
    proof_target = workspace.llm_backend_proof_path
    required = [target, presentation_brief_target, canonical_generation_profile_target, slide_function_outline_target, proof_target]
    if _should_skip(required, force=force, resume_skip_completed=config.resume_skip_completed):
        return StageExecution(stage="gate1-plan", skipped=True, written=required, detail="workflow_plan already exists.")
    workflow_plan, proof = plan_workflow_from_file_with_provider(
        workspace.brief_path,
        provider_settings=config.provider,
        llm_backend_proof_path=proof_target,
    )
    if workflow_plan.slide_ratio != config.slide_ratio:
        workflow_plan = workflow_plan.model_copy(update={"slide_ratio": config.slide_ratio})
    save_state_file(workflow_plan, target)
    if workflow_plan.presentation_brief is not None:
        save_state_file(workflow_plan.presentation_brief, presentation_brief_target)
    if workflow_plan.canonical_generation_profile is not None:
        save_state_file(workflow_plan.canonical_generation_profile, canonical_generation_profile_target)
    if workflow_plan.slide_function_outline is not None:
        save_state_file(workflow_plan.slide_function_outline, slide_function_outline_target)
    detail = (
        "Generated workflow plan from the configured brief. "
        f"Provider={proof.provider_used}, transport={proof.transport_used}, llm_requests={proof.llm_request_count}."
    )
    return StageExecution(stage="gate1-plan", skipped=False, written=required, detail=detail)


def _maybe_scan_reference_dna(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> list[Path]:
    if workspace.reference_pack_path is None:
        return []
    reference_target = workspace.state_path("reference_dna")
    if _should_skip([reference_target], force=force, resume_skip_completed=config.resume_skip_completed):
        return [reference_target]
    workflow_plan = load_state_file(workspace.state_path("workflow_plan"))
    reference_dna = scan_reference_pack(workspace.reference_pack_path, workflow_plan=workflow_plan)
    save_state_file(reference_dna, reference_target)
    return [reference_target]


def run_gate2_blueprint(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> StageExecution:
    _require_trusted_execution("run_gate2_blueprint")
    workflow_plan_path = workspace.state_path("workflow_plan")
    proof_unit_registry_path = workspace.state_path("proof_unit_registry")
    proof_module_manifest_path = workspace.state_path("proof_module_manifest")
    if workflow_plan_path.is_file():
        workflow_plan = load_state_file(workflow_plan_path)
        workflow_option = str(getattr(workflow_plan, "workflow_option", "")) or None
        if shared_proof_consumer_policy(workflow_option) is None:
            if proof_unit_registry_path.is_file():
                proof_unit_registry_path.unlink()
        if proof_module_manifest_path.is_file():
            proof_module_manifest_path.unlink()
    required = legacy_stage_artifacts("gate2-blueprint", workspace)
    if _should_skip(required, force=force, resume_skip_completed=config.resume_skip_completed):
        return StageExecution(stage="gate2-blueprint", skipped=True, written=required, detail="Gate 2 blueprint and orchestration artifacts already exist.")

    written: list[Path] = []
    if not workspace.state_path("workflow_plan").is_file():
        run_gate1_plan(config, workspace, force=False)
    written.extend(_maybe_scan_reference_dna(config, workspace, force=force))
    outputs = plan_gate2_from_files(
        workflow_plan_path=workspace.state_path("workflow_plan"),
        brief_path=workspace.brief_path,
        reference_dna_path=workspace.state_path("reference_dna") if workspace.state_path("reference_dna").is_file() else None,
        brand_inputs_path=workspace.brand_inputs_path,
    )
    blueprint = outputs.blueprint
    if config.blueprint_approved:
        blueprint = blueprint.model_copy(update={"approval_status": StageStatus.APPROVED})
        outputs = outputs.model_copy(update={"blueprint": blueprint})
    written.extend(write_gate2_outputs(outputs, workspace.state_dir).values())

    orchestration_outputs = orchestrate_large_deck_from_files(
        workflow_plan_path=workspace.state_path("workflow_plan"),
        blueprint_path=workspace.state_path("blueprint"),
        design_system_path=workspace.state_path("design_system"),
        deck_constitution_path=workspace.state_path("deck_constitution"),
        layout_library_path=workspace.state_path("layout_library"),
        slide_ledger_path=workspace.state_path("slide_ledger"),
        pointer_root=workspace.state_dir.as_posix(),
        batch_size_overrides=config.batch_parameters.as_override_map(),
    )
    if config.blueprint_approved and orchestration_outputs.state_capsule is not None:
        orchestration_outputs = orchestration_outputs.model_copy(
            update={
                "state_capsule": orchestration_outputs.state_capsule.model_copy(update={"blueprint_approved": True})
            }
        )
    written.extend(write_large_deck_outputs(orchestration_outputs, workspace.state_dir).values())
    detail = "Generated Gate 2 blueprint, reference, and long-deck orchestration state."
    if config.blueprint_approved:
        detail += " Blueprint approval was represented in state."
    return StageExecution(stage="gate2-blueprint", skipped=False, written=_dedupe_paths(written), detail=detail)


def run_derive_assets(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> StageExecution:
    _require_trusted_execution("run_derive_assets")
    required = legacy_stage_artifacts("derive-assets", workspace)
    if _should_skip(required, force=force, resume_skip_completed=config.resume_skip_completed):
        return StageExecution(stage="derive-assets", skipped=True, written=required, detail="Phase 5 production-handoff artifacts already exist.")
    outputs = derive_assets_from_files(
        blueprint_path=workspace.state_path("blueprint"),
        design_system_path=workspace.state_path("design_system"),
        deck_constitution_path=workspace.state_path("deck_constitution"),
        layout_library_path=workspace.state_path("layout_library"),
        slide_ledger_path=workspace.state_path("slide_ledger"),
        asset_requests_path=workspace.state_path("asset_requests") if workspace.state_path("asset_requests").is_file() else None,
    )
    written = list(write_asset_derivation_outputs(outputs, workspace.state_dir).values())
    return StageExecution(
        stage="derive-assets",
        skipped=False,
        written=_dedupe_paths(written),
        detail="Normalized Gate 2 asset requests, generated viz_spec handoff state, and refreshed the slide ledger.",
    )


def run_extract_assets(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> StageExecution:
    _require_trusted_execution("run_extract_assets")
    required = legacy_stage_artifacts("extract-assets", workspace)
    if _should_skip(required, force=force, resume_skip_completed=config.resume_skip_completed):
        return StageExecution(stage="extract-assets", skipped=True, written=required, detail="Crop outputs already exist.")
    asset_manifest_path = workspace.state_path("asset_manifest")
    outputs = run_document_asset_crop_from_files(
        asset_requests_path=workspace.state_path("asset_requests"),
        slide_ledger_path=workspace.state_path("slide_ledger"),
        output_dir=workspace.asset_dir,
        asset_manifest_path=asset_manifest_path if asset_manifest_path.is_file() else None,
        dpi=config.render_dpi,
        max_candidates_per_source=config.max_crop_candidates_per_source,
        max_review_rounds=config.crop_review_loop_limit,
        root=workspace.base_dir,
    )
    written = list(write_document_crop_outputs(outputs, workspace.asset_dir).values())
    save_state_file(outputs.asset_manifest, asset_manifest_path)
    save_state_file(outputs.slide_ledger, workspace.state_path("slide_ledger"))
    written.extend([asset_manifest_path, workspace.state_path("slide_ledger")])
    return StageExecution(
        stage="extract-assets",
        skipped=False,
        written=_dedupe_paths(written),
        detail="Rendered crop candidates, normalized direct source-reuse assets, and synchronized crop manifests for later review.",
    )


def run_review_crops(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> StageExecution:
    _require_trusted_execution("run_review_crops")
    required = legacy_stage_artifacts("review-crops", workspace)
    crop_candidates_path = workspace.asset_dir / "crop-candidates.json"
    crop_review_inputs_path = workspace.asset_dir / "crop-review-inputs.json"
    crop_review_decisions_path = workspace.asset_dir / "crop-review-decisions.json"
    selected_crops_path = workspace.asset_dir / "selected-crops.json"
    asset_manifest_path = workspace.asset_dir / "asset-manifest.json"
    slide_ledger_path = workspace.asset_dir / "slide-ledger.json"

    extraction_inputs = [crop_candidates_path, asset_manifest_path, slide_ledger_path]
    if force or not all(path.is_file() for path in extraction_inputs):
        run_extract_assets(config, workspace, force=True)

    manifest_source = asset_manifest_path if asset_manifest_path.is_file() else workspace.state_path("asset_manifest")
    manifest = load_state_file(manifest_source)
    if manifest.schema_name != "asset_manifest":
        raise TypeError(f"expected asset_manifest, found {manifest.schema_name}")
    review_transition = determine_crop_review_transition(manifest)

    if (not force) and review_transition.can_skip_crop_review and all(path.is_file() for path in required):
        for path in required:
            load_document_crop_file(path)
        save_state_file(manifest, workspace.state_path("asset_manifest"))
        if slide_ledger_path.is_file():
            save_state_file(load_state_file(slide_ledger_path), workspace.state_path("slide_ledger"))
        return StageExecution(
            stage="review-crops",
            skipped=True,
            written=[*required, workspace.state_path("asset_manifest"), workspace.state_path("slide_ledger")],
            detail="No crop requests remain pending review; accepted crop artifacts were synchronized back into canonical state.",
        )

    outputs = run_document_crop_review_from_files(
        asset_requests_path=workspace.state_path("asset_requests"),
        slide_ledger_path=slide_ledger_path if slide_ledger_path.is_file() else workspace.state_path("slide_ledger"),
        crop_candidates_path=crop_candidates_path,
        asset_manifest_path=asset_manifest_path,
        output_dir=workspace.asset_dir,
        crop_review_inputs_path=crop_review_inputs_path if crop_review_inputs_path.is_file() else None,
        crop_review_decisions_path=crop_review_decisions_path if crop_review_decisions_path.is_file() else None,
        selected_crops_path=selected_crops_path if selected_crops_path.is_file() else None,
        max_review_rounds=config.crop_review_loop_limit,
        root=workspace.base_dir,
    )
    written = list(write_document_crop_outputs(outputs, workspace.asset_dir).values())
    save_state_file(outputs.asset_manifest, workspace.state_path("asset_manifest"))
    save_state_file(outputs.slide_ledger, workspace.state_path("slide_ledger"))
    written.extend([workspace.state_path("asset_manifest"), workspace.state_path("slide_ledger")])
    return StageExecution(
        stage="review-crops",
        skipped=False,
        written=_dedupe_paths(written),
        detail="Ran bounded crop review, promoted accepted selections into compile-ready assets, and synchronized crop state.",
    )


def run_render_visuals(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> StageExecution:
    _require_trusted_execution("run_render_visuals")
    required = legacy_stage_artifacts("render-visuals", workspace)
    if _should_skip(required, force=force, resume_skip_completed=config.resume_skip_completed):
        return StageExecution(stage="render-visuals", skipped=True, written=required, detail="Structured visual outputs already exist.")
    if not workspace.state_path("viz_spec").is_file():
        run_derive_assets(config, workspace, force=False)
    viz_manifest_path = workspace.state_path("viz_manifest")
    asset_manifest_path = workspace.state_path("asset_manifest")
    outputs = run_structured_visuals_from_files(
        viz_spec_path=workspace.state_path("viz_spec"),
        design_system_path=workspace.state_path("design_system"),
        deck_constitution_path=workspace.state_path("deck_constitution"),
        layout_library_path=workspace.state_path("layout_library"),
        slide_ledger_path=workspace.state_path("slide_ledger"),
        output_dir=workspace.visual_dir,
        asset_requests_path=workspace.state_path("asset_requests") if workspace.state_path("asset_requests").is_file() else None,
        asset_manifest_path=asset_manifest_path if asset_manifest_path.is_file() else None,
        viz_manifest_path=viz_manifest_path if viz_manifest_path.is_file() else None,
        root=workspace.base_dir,
    )
    written = list(write_structured_visual_outputs(outputs, workspace.visual_dir).values())
    save_state_file(outputs.viz_manifest, viz_manifest_path)
    save_state_file(outputs.asset_manifest, asset_manifest_path)
    save_state_file(outputs.slide_ledger, workspace.state_path("slide_ledger"))
    written.extend([viz_manifest_path, asset_manifest_path, workspace.state_path("slide_ledger")])
    return StageExecution(
        stage="render-visuals",
        skipped=False,
        written=_dedupe_paths(written),
        detail="Rendered deterministic structured visuals from viz_spec and synchronized visual plus asset manifests into state.",
    )


def run_compile_pptx(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> StageExecution:
    _require_trusted_execution("run_compile_pptx")
    if not config.blueprint_approved:
        raise ValueError("compile-pptx requires blueprint_approved=true in the runtime config so Gate 2 approval is represented in state.")
    required = [
        workspace.deck_build_dir / "build-manifest.json",
        workspace.deck_build_dir / "slide-build-linkage.json",
        workspace.deck_build_dir / "slide-ledger.json",
        workspace.deck_build_dir / config.pptx_name,
    ]
    if _should_skip(required, force=force, resume_skip_completed=config.resume_skip_completed):
        return StageExecution(stage="compile-pptx", skipped=True, written=required, detail="Compiled PPTX artifacts already exist.")
    outputs = compile_pptx_from_files(
        blueprint_path=workspace.state_path("blueprint"),
        design_system_path=workspace.state_path("design_system"),
        deck_constitution_path=workspace.state_path("deck_constitution"),
        layout_library_path=workspace.state_path("layout_library"),
        slide_ledger_path=workspace.state_path("slide_ledger"),
        asset_manifest_path=workspace.state_path("asset_manifest"),
        viz_manifest_path=workspace.state_path("viz_manifest"),
        output_dir=workspace.deck_build_dir,
        batch_manifest_path=workspace.state_path("batch_manifest") if workspace.state_path("batch_manifest").is_file() else None,
        state_capsule_path=workspace.state_path("state_capsule") if workspace.state_path("state_capsule").is_file() else None,
        notes_path=workspace.notes_path if workspace.notes_path is not None and workspace.notes_path.is_file() else None,
        pptx_name=config.pptx_name,
        root=workspace.base_dir,
    )
    written = list(write_pptx_compile_outputs(outputs, workspace.deck_build_dir).values())
    save_state_file(outputs.slide_ledger, workspace.state_path("slide_ledger"))
    written.append(workspace.state_path("slide_ledger"))
    if outputs.batch_manifest is not None:
        save_state_file(outputs.batch_manifest, workspace.state_path("batch_manifest"))
        written.append(workspace.state_path("batch_manifest"))
    if outputs.state_capsule is not None:
        save_state_file(outputs.state_capsule, workspace.state_path("state_capsule"))
        written.append(workspace.state_path("state_capsule"))
    return StageExecution(stage="compile-pptx", skipped=False, written=_dedupe_paths(written + [outputs.pptx_path]), detail="Compiled the approved blueprint package into a PPTX and persisted compile manifests.")


def run_qa_deck(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> StageExecution:
    _require_trusted_execution("run_qa_deck")
    required = legacy_stage_artifacts("qa-deck", workspace)
    if _should_skip(required, force=force, resume_skip_completed=config.resume_skip_completed):
        return StageExecution(stage="qa-deck", skipped=True, written=required, detail="qa_report already exists.")
    outputs = run_deck_qa_from_files(
        blueprint_path=workspace.state_path("blueprint"),
        design_system_path=workspace.state_path("design_system"),
        deck_constitution_path=workspace.state_path("deck_constitution"),
        layout_library_path=workspace.state_path("layout_library"),
        slide_ledger_path=workspace.state_path("slide_ledger"),
        asset_manifest_path=workspace.state_path("asset_manifest"),
        viz_manifest_path=workspace.state_path("viz_manifest"),
        build_manifest_path=workspace.deck_build_dir / "build-manifest.json",
        slide_build_linkage_path=workspace.deck_build_dir / "slide-build-linkage.json",
        state_capsule_path=workspace.state_path("state_capsule") if workspace.state_path("state_capsule").is_file() else None,
        prior_report_path=workspace.state_path("qa_report") if workspace.state_path("qa_report").is_file() else None,
        qa_governance_path=workspace.state_path("qa_governance") if workspace.state_path("qa_governance").is_file() else None,
        artifact_root=workspace.base_dir,
    )
    save_state_file(outputs.qa_report, workspace.state_path("qa_report"))
    if outputs.qa_governance is not None:
        save_state_file(outputs.qa_governance, workspace.state_path("qa_governance"))
    save_state_file(outputs.slide_ledger, workspace.state_path("slide_ledger"))
    save_state_file(outputs.slide_build_linkage, workspace.deck_build_dir / "slide-build-linkage.json")
    written = [workspace.state_path("qa_report"), workspace.state_path("slide_ledger"), workspace.deck_build_dir / "slide-build-linkage.json"]
    if outputs.qa_governance is not None:
        written.append(workspace.state_path("qa_governance"))
    if outputs.state_capsule is not None:
        save_state_file(outputs.state_capsule, workspace.state_path("state_capsule"))
        written.append(workspace.state_path("state_capsule"))
    return StageExecution(stage="qa-deck", skipped=False, written=written, detail="Ran deterministic deck QA and persisted bounded remediation guidance.")


def run_orchestrate_large_deck(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> StageExecution:
    _require_trusted_execution("run_orchestrate_large_deck")
    required = legacy_stage_artifacts("orchestrate-large-deck", workspace)
    if _should_skip(required, force=force, resume_skip_completed=config.resume_skip_completed):
        return StageExecution(stage="orchestrate-large-deck", skipped=True, written=required, detail="Long-deck control-state artifacts already exist.")
    qa_inputs = [
        workspace.state_path("workflow_plan"),
        workspace.state_path("blueprint"),
        workspace.state_path("design_system"),
        workspace.state_path("deck_constitution"),
        workspace.state_path("layout_library"),
        workspace.state_path("slide_ledger"),
        workspace.state_path("qa_report"),
        workspace.deck_build_dir / "build-manifest.json",
        workspace.deck_build_dir / "slide-build-linkage.json",
    ]
    if force or not all(path.is_file() for path in qa_inputs):
        run_qa_deck(config, workspace, force=True)

    outputs = orchestrate_large_deck_from_files(
        workflow_plan_path=workspace.state_path("workflow_plan"),
        blueprint_path=workspace.state_path("blueprint"),
        design_system_path=workspace.state_path("design_system"),
        deck_constitution_path=workspace.state_path("deck_constitution"),
        layout_library_path=workspace.state_path("layout_library"),
        slide_ledger_path=workspace.state_path("slide_ledger"),
        build_manifest_path=workspace.deck_build_dir / "build-manifest.json",
        slide_build_linkage_path=workspace.deck_build_dir / "slide-build-linkage.json",
        qa_report_path=workspace.state_path("qa_report"),
        pointer_root=workspace.state_dir.as_posix(),
        canonical_state_root=workspace.state_dir.as_posix(),
    )
    written = list(write_large_deck_outputs(outputs, workspace.orchestration_dir).values())
    for schema_name in ("batch_manifest", "context_lock", "handoff_packet", "state_capsule", "remediation_plan", "slide_ledger"):
        save_state_file(getattr(outputs, schema_name), workspace.state_path(schema_name))
        written.append(workspace.state_path(schema_name))
    if outputs.slide_build_linkage is not None:
        save_state_file(outputs.slide_build_linkage, workspace.deck_build_dir / "slide-build-linkage.json")
        written.append(workspace.deck_build_dir / "slide-build-linkage.json")
    return StageExecution(
        stage="orchestrate-large-deck",
        skipped=False,
        written=_dedupe_paths(written),
        detail="Refreshed batch, continuation, and remediation-control artifacts from the built deck and current QA state.",
    )


def run_apply_remediation(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> StageExecution:
    _require_trusted_execution("run_apply_remediation")
    required = legacy_stage_artifacts("apply-remediation", workspace)
    if _should_skip(required, force=force, resume_skip_completed=config.resume_skip_completed):
        return StageExecution(stage="apply-remediation", skipped=True, written=required, detail="Bounded remediation execution report already exists.")

    remediation_inputs = [
        workspace.state_path("remediation_plan"),
        workspace.state_path("batch_manifest"),
        workspace.state_path("context_lock"),
        workspace.state_path("state_capsule"),
        workspace.state_path("slide_ledger"),
        workspace.state_path("qa_report"),
        workspace.state_path("qa_governance"),
        workspace.deck_build_dir / "build-manifest.json",
        workspace.deck_build_dir / "slide-build-linkage.json",
        workspace.state_path("blueprint"),
        workspace.state_path("design_system"),
        workspace.state_path("deck_constitution"),
        workspace.state_path("layout_library"),
        workspace.state_path("asset_manifest"),
        workspace.state_path("viz_manifest"),
    ]
    if force or not all(path.is_file() for path in remediation_inputs):
        run_orchestrate_large_deck(config, workspace, force=True)

    outputs = apply_bounded_remediation_from_files(
        remediation_plan_path=workspace.state_path("remediation_plan"),
        batch_manifest_path=workspace.state_path("batch_manifest"),
        context_lock_path=workspace.state_path("context_lock"),
        state_capsule_path=workspace.state_path("state_capsule"),
        slide_ledger_path=workspace.state_path("slide_ledger"),
        slide_build_linkage_path=workspace.deck_build_dir / "slide-build-linkage.json",
        qa_report_path=workspace.state_path("qa_report"),
        build_manifest_path=workspace.deck_build_dir / "build-manifest.json",
        blueprint_path=workspace.state_path("blueprint"),
        design_system_path=workspace.state_path("design_system"),
        deck_constitution_path=workspace.state_path("deck_constitution"),
        layout_library_path=workspace.state_path("layout_library"),
        asset_manifest_path=workspace.state_path("asset_manifest"),
        viz_manifest_path=workspace.state_path("viz_manifest"),
        workflow_plan_path=workspace.state_path("workflow_plan") if workspace.state_path("workflow_plan").is_file() else None,
        handoff_packet_path=workspace.state_path("handoff_packet") if workspace.state_path("handoff_packet").is_file() else None,
        asset_requests_path=workspace.state_path("asset_requests") if workspace.state_path("asset_requests").is_file() else None,
        viz_spec_path=workspace.state_path("viz_spec") if workspace.state_path("viz_spec").is_file() else None,
        notes_path=workspace.notes_path if workspace.notes_path is not None and workspace.notes_path.is_file() else None,
        artifact_root=workspace.base_dir,
        state_output_dir=workspace.state_dir,
        build_output_dir=workspace.deck_build_dir,
        visual_output_dir=workspace.visual_dir,
    )
    written = list(
        write_remediation_execution_outputs(
            outputs,
            workspace.state_dir,
            build_output_dir=workspace.deck_build_dir,
        ).values()
    )
    return StageExecution(
        stage="apply-remediation",
        skipped=False,
        written=_dedupe_paths(written),
        detail="Applied bounded remediation actions, reran only required downstream stages, and refreshed canonical control plus QA artifacts.",
    )


def run_author_upstream_fixes(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> StageExecution:
    _require_trusted_execution("run_author_upstream_fixes")
    required = legacy_stage_artifacts("author-upstream-fixes", workspace)
    if _should_skip(required, force=force, resume_skip_completed=config.resume_skip_completed):
        return StageExecution(stage="author-upstream-fixes", skipped=True, written=required, detail="Upstream-fix approval artifacts already exist.")

    upstream_inputs = [
        workspace.state_path("remediation_plan"),
        workspace.state_path("remediation_execution_report"),
        workspace.state_path("batch_manifest"),
        workspace.state_path("context_lock"),
        workspace.state_path("handoff_packet"),
        workspace.state_path("state_capsule"),
        workspace.state_path("slide_ledger"),
        workspace.state_path("qa_report"),
        workspace.state_path("qa_governance"),
        workspace.deck_build_dir / "build-manifest.json",
        workspace.deck_build_dir / "slide-build-linkage.json",
        workspace.state_path("blueprint"),
        workspace.state_path("design_system"),
        workspace.state_path("deck_constitution"),
        workspace.state_path("layout_library"),
        workspace.state_path("asset_manifest"),
        workspace.state_path("viz_manifest"),
    ]
    if force or not all(path.is_file() for path in upstream_inputs):
        run_apply_remediation(config, workspace, force=True)

    outputs = author_upstream_fixes_from_files(
        remediation_plan_path=workspace.state_path("remediation_plan"),
        remediation_execution_report_path=workspace.state_path("remediation_execution_report"),
        batch_manifest_path=workspace.state_path("batch_manifest"),
        context_lock_path=workspace.state_path("context_lock"),
        handoff_packet_path=workspace.state_path("handoff_packet"),
        state_capsule_path=workspace.state_path("state_capsule"),
        slide_ledger_path=workspace.state_path("slide_ledger"),
        slide_build_linkage_path=workspace.deck_build_dir / "slide-build-linkage.json",
        qa_report_path=workspace.state_path("qa_report"),
        build_manifest_path=workspace.deck_build_dir / "build-manifest.json",
        blueprint_path=workspace.state_path("blueprint"),
        design_system_path=workspace.state_path("design_system"),
        deck_constitution_path=workspace.state_path("deck_constitution"),
        layout_library_path=workspace.state_path("layout_library"),
        asset_manifest_path=workspace.state_path("asset_manifest"),
        viz_manifest_path=workspace.state_path("viz_manifest"),
        asset_requests_path=workspace.state_path("asset_requests") if workspace.state_path("asset_requests").is_file() else None,
        viz_spec_path=workspace.state_path("viz_spec") if workspace.state_path("viz_spec").is_file() else None,
        pointer_root=workspace.state_dir.as_posix(),
    )
    written = list(write_upstream_fix_outputs(outputs, workspace.state_dir).values())
    return StageExecution(
        stage="author-upstream-fixes",
        skipped=False,
        written=_dedupe_paths(written),
        detail="Prepared bounded upstream approval packets, machine-readable deltas, and synchronized control-state without applying deck changes.",
    )


def run_apply_approved_fixes(
    config: RuntimePipelineConfig,
    workspace: RuntimeWorkspace,
    *,
    force: bool = False,
    approved_packet_ids: list[str] | None = None,
    approved_fix_ids: list[str] | None = None,
    selected_delta_options: dict[str, str] | None = None,
) -> StageExecution:
    _require_trusted_execution("run_apply_approved_fixes")
    required = legacy_stage_artifacts("apply-approved-fixes", workspace)
    if _should_skip(required, force=force, resume_skip_completed=config.resume_skip_completed):
        return StageExecution(stage="apply-approved-fixes", skipped=True, written=required, detail="Approved-apply report already exists.")

    apply_inputs = [
        workspace.state_path("approval_packet"),
        workspace.state_path("authoring_deltas"),
        workspace.state_path("upstream_fix_plan"),
        workspace.state_path("remediation_plan"),
        workspace.state_path("remediation_execution_report"),
        workspace.state_path("batch_manifest"),
        workspace.state_path("context_lock"),
        workspace.state_path("state_capsule"),
        workspace.state_path("slide_ledger"),
        workspace.state_path("qa_report"),
        workspace.deck_build_dir / "build-manifest.json",
        workspace.deck_build_dir / "slide-build-linkage.json",
        workspace.state_path("blueprint"),
        workspace.state_path("design_system"),
        workspace.state_path("deck_constitution"),
        workspace.state_path("layout_library"),
        workspace.state_path("asset_manifest"),
        workspace.state_path("viz_manifest"),
    ]
    if force or not all(path.is_file() for path in apply_inputs):
        run_author_upstream_fixes(config, workspace, force=True)

    outputs = apply_approved_fixes_from_files(
        approval_packet_path=workspace.state_path("approval_packet"),
        authoring_deltas_path=workspace.state_path("authoring_deltas"),
        upstream_fix_plan_path=workspace.state_path("upstream_fix_plan"),
        remediation_plan_path=workspace.state_path("remediation_plan"),
        remediation_execution_report_path=workspace.state_path("remediation_execution_report"),
        batch_manifest_path=workspace.state_path("batch_manifest"),
        context_lock_path=workspace.state_path("context_lock"),
        state_capsule_path=workspace.state_path("state_capsule"),
        slide_ledger_path=workspace.state_path("slide_ledger"),
        slide_build_linkage_path=workspace.deck_build_dir / "slide-build-linkage.json",
        qa_report_path=workspace.state_path("qa_report"),
        build_manifest_path=workspace.deck_build_dir / "build-manifest.json",
        blueprint_path=workspace.state_path("blueprint"),
        design_system_path=workspace.state_path("design_system"),
        deck_constitution_path=workspace.state_path("deck_constitution"),
        layout_library_path=workspace.state_path("layout_library"),
        asset_manifest_path=workspace.state_path("asset_manifest"),
        viz_manifest_path=workspace.state_path("viz_manifest"),
        handoff_packet_path=workspace.state_path("handoff_packet") if workspace.state_path("handoff_packet").is_file() else None,
        workflow_plan_path=workspace.state_path("workflow_plan") if workspace.state_path("workflow_plan").is_file() else None,
        asset_requests_path=workspace.state_path("asset_requests") if workspace.state_path("asset_requests").is_file() else None,
        viz_spec_path=workspace.state_path("viz_spec") if workspace.state_path("viz_spec").is_file() else None,
        approved_packet_ids=approved_packet_ids,
        approved_fix_ids=approved_fix_ids,
        selected_delta_options=selected_delta_options,
        artifact_root=workspace.base_dir,
        state_output_dir=workspace.state_dir,
        build_output_dir=workspace.deck_build_dir,
        asset_output_dir=workspace.asset_dir,
        visual_output_dir=workspace.visual_dir,
        notes_path=workspace.notes_path if workspace.notes_path is not None and workspace.notes_path.is_file() else None,
    )
    written = list(
        write_approved_apply_outputs(
            outputs,
            workspace.state_dir,
            build_output_dir=workspace.deck_build_dir,
        ).values()
    )
    explicit_approvals = len(approved_packet_ids or []) + len(approved_fix_ids or [])
    detail = "Applied explicitly approved upstream deltas, reran only the required downstream stages, and refreshed canonical state."
    if explicit_approvals == 0:
        detail = "Prepared an approved-apply report from the current approval state without additional explicit CLI approvals."
    return StageExecution(
        stage="apply-approved-fixes",
        skipped=False,
        written=_dedupe_paths(written),
        detail=detail,
    )


def run_close_approved_fixes(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> StageExecution:
    _require_trusted_execution("run_close_approved_fixes")
    required = legacy_stage_artifacts("close-approved-fixes", workspace)
    if _should_skip(required, force=force, resume_skip_completed=config.resume_skip_completed):
        return StageExecution(stage="close-approved-fixes", skipped=True, written=required, detail="Post-apply closure artifacts already exist.")

    closure_inputs = [
        workspace.state_path("approved_apply_report"),
        workspace.state_path("approval_packet"),
        workspace.state_path("authoring_deltas"),
        workspace.state_path("upstream_fix_plan"),
        workspace.state_path("remediation_plan"),
        workspace.state_path("remediation_execution_report"),
        workspace.state_path("batch_manifest"),
        workspace.state_path("context_lock"),
        workspace.state_path("handoff_packet"),
        workspace.state_path("state_capsule"),
        workspace.state_path("slide_ledger"),
        workspace.state_path("qa_report"),
        workspace.deck_build_dir / "build-manifest.json",
        workspace.deck_build_dir / "slide-build-linkage.json",
        workspace.state_path("blueprint"),
        workspace.state_path("design_system"),
        workspace.state_path("deck_constitution"),
        workspace.state_path("layout_library"),
        workspace.state_path("asset_manifest"),
        workspace.state_path("viz_manifest"),
    ]
    if force or not all(path.is_file() for path in closure_inputs):
        run_apply_approved_fixes(config, workspace, force=True)

    outputs = close_approved_fixes_from_files(
        approved_apply_report_path=workspace.state_path("approved_apply_report"),
        approval_packet_path=workspace.state_path("approval_packet"),
        authoring_deltas_path=workspace.state_path("authoring_deltas"),
        upstream_fix_plan_path=workspace.state_path("upstream_fix_plan"),
        remediation_plan_path=workspace.state_path("remediation_plan"),
        remediation_execution_report_path=workspace.state_path("remediation_execution_report"),
        batch_manifest_path=workspace.state_path("batch_manifest"),
        context_lock_path=workspace.state_path("context_lock"),
        handoff_packet_path=workspace.state_path("handoff_packet"),
        state_capsule_path=workspace.state_path("state_capsule"),
        slide_ledger_path=workspace.state_path("slide_ledger"),
        slide_build_linkage_path=workspace.deck_build_dir / "slide-build-linkage.json",
        qa_report_path=workspace.state_path("qa_report"),
        build_manifest_path=workspace.deck_build_dir / "build-manifest.json",
        blueprint_path=workspace.state_path("blueprint"),
        design_system_path=workspace.state_path("design_system"),
        deck_constitution_path=workspace.state_path("deck_constitution"),
        layout_library_path=workspace.state_path("layout_library"),
        asset_manifest_path=workspace.state_path("asset_manifest"),
        viz_manifest_path=workspace.state_path("viz_manifest"),
        asset_requests_path=workspace.state_path("asset_requests") if workspace.state_path("asset_requests").is_file() else None,
        viz_spec_path=workspace.state_path("viz_spec") if workspace.state_path("viz_spec").is_file() else None,
        pointer_root=workspace.state_dir.as_posix(),
    )
    written = list(write_post_apply_closure_outputs(outputs, workspace.state_dir).values())
    return StageExecution(
        stage="close-approved-fixes",
        skipped=False,
        written=_dedupe_paths(written),
        detail="Closed applied approval packets, emitted a deterministic remaining backlog view, and synchronized control-state for the next run.",
    )


def run_assess_ship_readiness(config: RuntimePipelineConfig, workspace: RuntimeWorkspace, *, force: bool = False) -> StageExecution:
    _require_trusted_execution("run_assess_ship_readiness")
    required = legacy_stage_artifacts("assess-ship-readiness", workspace)
    if _should_skip(required, force=force, resume_skip_completed=config.resume_skip_completed):
        return StageExecution(stage="assess-ship-readiness", skipped=True, written=required, detail="Ship-readiness and cycle-reset artifacts already exist.")

    readiness_inputs = [
        workspace.state_path("closure_report"),
        workspace.state_path("remaining_backlog"),
        workspace.state_path("approval_packet"),
        workspace.state_path("authoring_deltas"),
        workspace.state_path("upstream_fix_plan"),
        workspace.state_path("approved_apply_report"),
        workspace.state_path("remediation_plan"),
        workspace.state_path("remediation_execution_report"),
        workspace.state_path("batch_manifest"),
        workspace.state_path("context_lock"),
        workspace.state_path("handoff_packet"),
        workspace.state_path("state_capsule"),
        workspace.state_path("slide_ledger"),
        workspace.state_path("qa_report"),
        workspace.state_path("qa_governance"),
        workspace.deck_build_dir / "build-manifest.json",
        workspace.deck_build_dir / "slide-build-linkage.json",
        workspace.state_path("blueprint"),
        workspace.state_path("design_system"),
        workspace.state_path("deck_constitution"),
        workspace.state_path("layout_library"),
        workspace.state_path("asset_manifest"),
        workspace.state_path("viz_manifest"),
    ]
    if force or not all(path.is_file() for path in readiness_inputs):
        run_close_approved_fixes(config, workspace, force=True)

    outputs = assess_ship_readiness_from_files(
        closure_report_path=workspace.state_path("closure_report"),
        remaining_backlog_path=workspace.state_path("remaining_backlog"),
        approval_packet_path=workspace.state_path("approval_packet"),
        authoring_deltas_path=workspace.state_path("authoring_deltas"),
        upstream_fix_plan_path=workspace.state_path("upstream_fix_plan"),
        approved_apply_report_path=workspace.state_path("approved_apply_report"),
        remediation_plan_path=workspace.state_path("remediation_plan"),
        remediation_execution_report_path=workspace.state_path("remediation_execution_report"),
        batch_manifest_path=workspace.state_path("batch_manifest"),
        context_lock_path=workspace.state_path("context_lock"),
        handoff_packet_path=workspace.state_path("handoff_packet"),
        state_capsule_path=workspace.state_path("state_capsule"),
        slide_ledger_path=workspace.state_path("slide_ledger"),
        slide_build_linkage_path=workspace.deck_build_dir / "slide-build-linkage.json",
        qa_report_path=workspace.state_path("qa_report"),
        qa_governance_path=workspace.state_path("qa_governance"),
        build_manifest_path=workspace.deck_build_dir / "build-manifest.json",
        blueprint_path=workspace.state_path("blueprint"),
        design_system_path=workspace.state_path("design_system"),
        deck_constitution_path=workspace.state_path("deck_constitution"),
        layout_library_path=workspace.state_path("layout_library"),
        asset_manifest_path=workspace.state_path("asset_manifest"),
        viz_manifest_path=workspace.state_path("viz_manifest"),
        artifact_root=workspace.base_dir,
        state_output_dir=workspace.state_dir,
    )
    written = list(write_ship_readiness_outputs(outputs, workspace.state_dir).values())
    detail = "Assessed ship readiness from the current closure/backlog state and synchronized cycle-reset control artifacts."
    if outputs.release_candidate is not None:
        detail += " Release-candidate.json was emitted because the deck is ship-ready."
    return StageExecution(
        stage="assess-ship-readiness",
        skipped=False,
        written=_dedupe_paths(written),
        detail=detail,
    )


def validate_runtime_state(paths: list[Path]) -> int:
    failures = 0
    for root in paths:
        if root.is_file():
            candidates = [root]
        elif root.is_dir():
            candidates = sorted(candidate for candidate in root.rglob("*") if candidate.is_file() and candidate.suffix.lower() in {".json", ".yaml", ".yml"})
        else:
            raise FileNotFoundError(root)
        for file_path in candidates:
            try:
                model = load_state_file(file_path)
            except Exception:
                try:
                    if file_path.name == "llm-backend-proof.json":
                        model = LLMBackendProof.model_validate_json(file_path.read_text(encoding="utf-8"))
                        print(f"VALID   {file_path} -> llm_backend_proof")
                        continue
                except Exception:
                    pass
                try:
                    model = load_document_crop_file(file_path)
                except Exception:
                    try:
                        model = load_pptx_compile_file(file_path)
                    except Exception as exc:
                        failures += 1
                        print(f"INVALID {file_path}: {exc}")
                    else:
                        print(f"VALID   {file_path} -> {model.schema_name}")
                else:
                    print(f"VALID   {file_path} -> {model.schema_name}")
            else:
                print(f"VALID   {file_path} -> {model.schema_name}")
    return 1 if failures else 0


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    return ordered


def run_stage(
    stage: str,
    config: RuntimePipelineConfig,
    workspace: RuntimeWorkspace,
    *,
    force: bool = False,
    approved_packet_ids: list[str] | None = None,
    approved_fix_ids: list[str] | None = None,
    selected_delta_options: dict[str, str] | None = None,
) -> StageExecution:
    _require_trusted_execution("run_stage")
    ensure_runtime_dirs(workspace)
    if stage == "gate1-plan":
        return run_gate1_plan(config, workspace, force=force)
    if stage == "gate2-blueprint":
        return run_gate2_blueprint(config, workspace, force=force)
    if stage == "derive-assets":
        return run_derive_assets(config, workspace, force=force)
    if stage == "extract-assets":
        return run_extract_assets(config, workspace, force=force)
    if stage == "review-crops":
        return run_review_crops(config, workspace, force=force)
    if stage == "render-visuals":
        return run_render_visuals(config, workspace, force=force)
    if stage == "compile-pptx":
        return run_compile_pptx(config, workspace, force=force)
    if stage == "qa-deck":
        return run_qa_deck(config, workspace, force=force)
    if stage == "orchestrate-large-deck":
        return run_orchestrate_large_deck(config, workspace, force=force)
    if stage == "apply-remediation":
        return run_apply_remediation(config, workspace, force=force)
    if stage == "author-upstream-fixes":
        return run_author_upstream_fixes(config, workspace, force=force)
    if stage == "apply-approved-fixes":
        return run_apply_approved_fixes(
            config,
            workspace,
            force=force,
            approved_packet_ids=approved_packet_ids,
            approved_fix_ids=approved_fix_ids,
            selected_delta_options=selected_delta_options,
        )
    if stage == "close-approved-fixes":
        return run_close_approved_fixes(config, workspace, force=force)
    if stage == "assess-ship-readiness":
        return run_assess_ship_readiness(config, workspace, force=force)
    raise KeyError(f"unknown stage {stage!r}")


def run_pipeline(
    config: RuntimePipelineConfig,
    workspace: RuntimeWorkspace,
    *,
    from_stage: str | None = None,
    to_stage: str | None = None,
    force_stages: set[str] | None = None,
) -> list[StageExecution]:
    _require_trusted_execution("run_pipeline")
    if from_stage is not None and from_stage not in LEGACY_RUNTIME_STAGE_ORDER:
        raise KeyError(f"unknown from_stage {from_stage!r}")
    if to_stage is not None and to_stage not in LEGACY_RUNTIME_STAGE_ORDER:
        raise KeyError(f"unknown to_stage {to_stage!r}")

    force = force_stages or set()
    start_index = LEGACY_RUNTIME_STAGE_ORDER.index(from_stage) if from_stage is not None else 0
    end_index = LEGACY_RUNTIME_STAGE_ORDER.index(to_stage) if to_stage is not None else len(LEGACY_RUNTIME_STAGE_ORDER) - 1
    if end_index < start_index:
        raise ValueError("to_stage must not come before from_stage")

    results: list[StageExecution] = []
    for stage in LEGACY_RUNTIME_STAGE_ORDER[start_index : end_index + 1]:
        results.append(run_stage(stage, config, workspace, force=stage in force))
    return results


