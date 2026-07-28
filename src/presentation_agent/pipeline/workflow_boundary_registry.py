"""Local-first boundary registry for workflow orchestration, skills, and tool surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .stages import PIPELINE_STAGE_ORDER, PipelineStage, coerce_stage


REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class SkillLikeCapability:
    capability_id: str
    summary: str
    owner_module: str
    entrypoints: tuple[str, ...]
    primary_stage: PipelineStage
    future_skill_candidate: bool = True
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExternalResourceBoundary:
    resource_id: str
    summary: str
    resource_kind: str
    bound_names: tuple[str, ...]
    owner_modules: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExternalToolBoundary:
    tool_id: str
    summary: str
    owner_module: str
    entrypoints: tuple[str, ...]
    acl_tool_names: tuple[str, ...]
    external_dependencies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptTemplateBoundary:
    prompt_id: str
    summary: str
    owner_module: str
    entrypoints: tuple[str, ...] = ()
    template_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowStageBoundary:
    stage: PipelineStage
    orchestration_role: str
    policy_owner_modules: tuple[str, ...]
    skill_capability_ids: tuple[str, ...] = ()
    resource_ids: tuple[str, ...] = ()
    tool_ids: tuple[str, ...] = ()
    prompt_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


SKILL_LIKE_CAPABILITIES: dict[str, SkillLikeCapability] = {
    "infer_brief": SkillLikeCapability(
        capability_id="infer_brief",
        summary="Infer the presentation brief contract from prompt-first inputs before layout work begins.",
        owner_module="presentation_agent.non_pptx_modules.workflow_planner",
        entrypoints=(
            "infer_workflow_brief_from_prompt",
            "_infer_presentation_brief",
            "plan_workflow",
            "plan_workflow_with_provider",
        ),
        primary_stage=PipelineStage.DESIGN_REFERENCE_CHECK,
    ),
    "assign_slide_function": SkillLikeCapability(
        capability_id="assign_slide_function",
        summary="Assign slide functions and content budgets before Gate 2 blueprint planning.",
        owner_module="presentation_agent.non_pptx_modules.workflow_planner",
        entrypoints=("_build_slide_function_outline", "plan_workflow"),
        primary_stage=PipelineStage.DESIGN_REFERENCE_CHECK,
    ),
    "extract_reference_style": SkillLikeCapability(
        capability_id="extract_reference_style",
        summary="Extract reusable reference-pack style signals without making slide-generation decisions.",
        owner_module="presentation_agent.non_pptx_modules.reference_scanner",
        entrypoints=("load_reference_brief_context", "scan_reference_pack"),
        primary_stage=PipelineStage.DESIGN_REFERENCE_CHECK,
    ),
    "brand_guard": SkillLikeCapability(
        capability_id="brand_guard",
        summary="Apply brand constraints and design-system policy during Gate 2 planning.",
        owner_module="presentation_agent.non_pptx_modules.gate2_planner",
        entrypoints=("load_brand_inputs", "_build_design_system", "plan_gate2"),
        primary_stage=PipelineStage.CONTENT_PLAN,
    ),
    "validate_slide_geometry": SkillLikeCapability(
        capability_id="validate_slide_geometry",
        summary="Validate slide-level geometry against SlideIR before final assembly is accepted.",
        owner_module="presentation_agent.pptx_compiler",
        entrypoints=("validate_slide_ir_geometry",),
        primary_stage=PipelineStage.RENDER_LOCAL_PPTX,
        future_skill_candidate=False,
    ),
    "validate_deck_consistency": SkillLikeCapability(
        capability_id="validate_deck_consistency",
        summary="Validate continuity and deck-level consistency findings without changing policy ownership.",
        owner_module="presentation_agent.pptx_compiler",
        entrypoints=("validate_slide_ir_continuity",),
        primary_stage=PipelineStage.QA,
        future_skill_candidate=False,
    ),
    "score_layout": SkillLikeCapability(
        capability_id="score_layout",
        summary="Score candidate layouts deterministically after SlideIR adaptation and before final compile.",
        owner_module="presentation_agent.pptx_compiler",
        entrypoints=("adapt_blueprint_to_slide_ir", "_score_layout_candidate"),
        primary_stage=PipelineStage.RENDER_LOCAL_PPTX,
        future_skill_candidate=False,
    ),
}


RESOURCE_BOUNDARIES: dict[str, ExternalResourceBoundary] = {
    "workflow_brief": ExternalResourceBoundary(
        resource_id="workflow_brief",
        summary="Primary brief payload and prompt-first request contract.",
        resource_kind="local-input",
        bound_names=("brief_path",),
        owner_modules=("presentation_agent.non_pptx_modules.runtime_config",),
    ),
    "reference_pack": ExternalResourceBoundary(
        resource_id="reference_pack",
        summary="Reference pack, PDF, image, or note bundle used for grounded style and structure hints.",
        resource_kind="local-input",
        bound_names=("reference_pack_path",),
        owner_modules=("presentation_agent.non_pptx_modules.reference_scanner",),
    ),
    "brand_inputs": ExternalResourceBoundary(
        resource_id="brand_inputs",
        summary="Brand or theme constraints consumed before blueprint planning.",
        resource_kind="local-input",
        bound_names=("brand_inputs_path",),
        owner_modules=("presentation_agent.non_pptx_modules.gate2_planner",),
    ),
    "notes_bundle": ExternalResourceBoundary(
        resource_id="notes_bundle",
        summary="Optional notes bundle treated as input evidence, not a workflow policy source.",
        resource_kind="local-input",
        bound_names=("notes_path",),
        owner_modules=("presentation_agent.pipeline.executors",),
    ),
    "workflow_state_bundle": ExternalResourceBoundary(
        resource_id="workflow_state_bundle",
        summary="State artifacts that carry the canonical workflow and planning contract across stages.",
        resource_kind="state-bundle",
        bound_names=(
            "state/workflow-plan.json",
            "state/presentation-brief.json",
            "state/canonical-generation-profile.json",
            "state/slide-function-outline.json",
            "state/reference-dna.json",
            "state/blueprint.json",
            "state/design-system.json",
            "state/layout-library.json",
            "state/slide-ledger.json",
        ),
        owner_modules=(
            "presentation_agent.non_pptx_modules.workflow_planner",
            "presentation_agent.non_pptx_modules.gate2_planner",
        ),
    ),
    "production_state_bundle": ExternalResourceBoundary(
        resource_id="production_state_bundle",
        summary="Deterministic production artifacts for assets, visuals, QA, and remediation-ready summaries.",
        resource_kind="state-bundle",
        bound_names=(
            "state/asset-requests.json",
            "state/asset-manifest.json",
            "state/viz-manifest.json",
            "state/qa-report.json",
            "outputs/runtime/assets",
            "outputs/runtime/visuals",
        ),
        owner_modules=("presentation_agent.non_pptx_modules.runtime_pipeline",),
    ),
    "compiled_deck_output": ExternalResourceBoundary(
        resource_id="compiled_deck_output",
        summary="Final local deck artifacts and deterministic compile manifests.",
        resource_kind="build-output",
        bound_names=(
            "outputs/runtime/deck-build/build-manifest.json",
            "outputs/runtime/deck-build/slide-build-linkage.json",
            "outputs/runtime/deck-build/deck.pptx",
        ),
        owner_modules=(
            "presentation_agent.non_pptx_modules.runtime_pipeline",
            "presentation_agent.pptx_compiler",
        ),
    ),
}


TOOL_BOUNDARIES: dict[str, ExternalToolBoundary] = {
    "filesystem_ingest": ExternalToolBoundary(
        tool_id="filesystem_ingest",
        summary="Read local inputs, classify assets, and fingerprint request materials.",
        owner_module="presentation_agent.pipeline.executors",
        entrypoints=("collect_pipeline_fingerprints", "_collect_ingest_assets"),
        acl_tool_names=("brief_intake", "asset_classification", "fingerprinting"),
        external_dependencies=("filesystem", "yaml/json parsing"),
    ),
    "provider_brief_intake": ExternalToolBoundary(
        tool_id="provider_brief_intake",
        summary="Provider-backed brief intake for structured workflow planning when enabled.",
        owner_module="presentation_agent.non_pptx_modules.provider_runtime",
        entrypoints=("run_brief_intake",),
        acl_tool_names=("workflow_planning",),
        external_dependencies=("urllib provider transport", "optional local/remote provider profiles"),
    ),
    "reference_pack_scan": ExternalToolBoundary(
        tool_id="reference_pack_scan",
        summary="Scan reference packs and emit grounded style/reference summaries.",
        owner_module="presentation_agent.non_pptx_modules.reference_scanner",
        entrypoints=("scan_reference_pack",),
        acl_tool_names=("reference_scan",),
        external_dependencies=("filesystem",),
    ),
    "template_bundle_write": ExternalToolBoundary(
        tool_id="template_bundle_write",
        summary="Write the approved template bundle and template-facing style tokens for downstream stages.",
        owner_module="presentation_agent.pipeline.executors",
        entrypoints=("_execute_master_template",),
        acl_tool_names=("template_schema_creation", "theme_token_definition", "template_bundle_write"),
    ),
    "gate2_blueprint_planning": ExternalToolBoundary(
        tool_id="gate2_blueprint_planning",
        summary="Run Gate 2 blueprint/design-system planning through the runtime adapter path.",
        owner_module="presentation_agent.non_pptx_modules.runtime_pipeline",
        entrypoints=("run_gate2_blueprint",),
        acl_tool_names=("blueprint_planning", "continuity_planning"),
    ),
    "asset_visual_production": ExternalToolBoundary(
        tool_id="asset_visual_production",
        summary="Run deterministic asset derivation, crop extraction/review, and structured visual rendering.",
        owner_module="presentation_agent.non_pptx_modules.runtime_pipeline",
        entrypoints=("run_derive_assets", "run_extract_assets", "run_review_crops", "run_render_visuals"),
        acl_tool_names=(
            "asset_request_derivation",
            "document_crop_rendering",
            "crop_review",
            "structured_visual_rendering",
        ),
    ),
    "deck_qa_audit": ExternalToolBoundary(
        tool_id="deck_qa_audit",
        summary="Run preflight render, deterministic QA, and continuity orchestration under the QA gate.",
        owner_module="presentation_agent.pipeline.executors",
        entrypoints=("_execute_qa",),
        acl_tool_names=("preflight_render", "deck_q_audit", "continuity_orchestration"),
    ),
    "local_pptx_compilation": ExternalToolBoundary(
        tool_id="local_pptx_compilation",
        summary="Compile the final local PPTX through the runtime adapter and SlideIR compiler path.",
        owner_module="presentation_agent.non_pptx_modules.runtime_pipeline",
        entrypoints=("run_compile_pptx",),
        acl_tool_names=("local_pptx_assembly",),
        external_dependencies=("python-pptx", "PIL", "cairosvg"),
    ),
    "local_render_validation": ExternalToolBoundary(
        tool_id="local_render_validation",
        summary="Validate the local PPTX archive and emit checksum/render metadata.",
        owner_module="presentation_agent.pipeline.render_validation",
        entrypoints=("validate_local_pptx",),
        acl_tool_names=("render_validation", "checksum_generation"),
    ),
}


PROMPT_TEMPLATE_BOUNDARIES: dict[str, PromptTemplateBoundary] = {
    "brief_intake_structured_prompt": PromptTemplateBoundary(
        prompt_id="brief_intake_structured_prompt",
        summary="Structured provider prompts used for the workflow-brief intake step.",
        owner_module="presentation_agent.non_pptx_modules.provider_runtime",
        entrypoints=("_build_system_prompt", "_build_initial_user_prompt", "_build_repair_user_prompt"),
    ),
    "harness_prompt_set": PromptTemplateBoundary(
        prompt_id="harness_prompt_set",
        summary="Prompt files that describe harness execution and deck-task orchestration policy.",
        owner_module="presentation_agent.pipeline.executors",
        template_paths=("prompts/implement_harness.md", "prompts/run_deck_task.md"),
    ),
}


WORKFLOW_STAGE_BOUNDARIES: dict[PipelineStage, WorkflowStageBoundary] = {
    PipelineStage.INGEST: WorkflowStageBoundary(
        stage=PipelineStage.INGEST,
        orchestration_role="Classify runtime inputs, fingerprint request contracts, and freeze ingest evidence before planning.",
        policy_owner_modules=("presentation_agent.pipeline.orchestrator", "presentation_agent.pipeline.executors"),
        resource_ids=("workflow_brief", "reference_pack", "brand_inputs", "notes_bundle"),
        tool_ids=("filesystem_ingest",),
        notes=("No slide-generation or policy decisions belong here.",),
    ),
    PipelineStage.DESIGN_REFERENCE_CHECK: WorkflowStageBoundary(
        stage=PipelineStage.DESIGN_REFERENCE_CHECK,
        orchestration_role="Sequence workflow planning and reference/style extraction without generating slides.",
        policy_owner_modules=("presentation_agent.pipeline.orchestrator", "presentation_agent.pipeline.tool_acl"),
        skill_capability_ids=("infer_brief", "assign_slide_function", "extract_reference_style"),
        resource_ids=("workflow_brief", "reference_pack", "brand_inputs"),
        tool_ids=("provider_brief_intake", "reference_pack_scan"),
        prompt_ids=("brief_intake_structured_prompt",),
    ),
    PipelineStage.MASTER_TEMPLATE: WorkflowStageBoundary(
        stage=PipelineStage.MASTER_TEMPLATE,
        orchestration_role="Freeze the approved template bundle and style-token basis before content planning.",
        policy_owner_modules=("presentation_agent.pipeline.orchestrator", "presentation_agent.pipeline.executors"),
        resource_ids=("workflow_state_bundle", "reference_pack", "brand_inputs"),
        tool_ids=("template_bundle_write",),
        prompt_ids=("harness_prompt_set",),
    ),
    PipelineStage.CONTENT_PLAN: WorkflowStageBoundary(
        stage=PipelineStage.CONTENT_PLAN,
        orchestration_role="Run Gate 2 blueprint/design-system planning while keeping workflow policy centralized.",
        policy_owner_modules=(
            "presentation_agent.pipeline.orchestrator",
            "presentation_agent.non_pptx_modules.workflow_contract_matrix",
        ),
        skill_capability_ids=("brand_guard",),
        resource_ids=("workflow_state_bundle", "reference_pack", "brand_inputs"),
        tool_ids=("gate2_blueprint_planning",),
    ),
    PipelineStage.GENERATE: WorkflowStageBoundary(
        stage=PipelineStage.GENERATE,
        orchestration_role="Invoke deterministic production workers after planning approvals are locked.",
        policy_owner_modules=("presentation_agent.pipeline.orchestrator", "presentation_agent.pipeline.executors"),
        resource_ids=("workflow_state_bundle", "production_state_bundle"),
        tool_ids=("asset_visual_production",),
    ),
    PipelineStage.QA: WorkflowStageBoundary(
        stage=PipelineStage.QA,
        orchestration_role="Run deterministic QA and continuity checks while keeping remediation policy in the harness.",
        policy_owner_modules=("presentation_agent.pipeline.orchestrator", "presentation_agent.pipeline.executors"),
        skill_capability_ids=("validate_deck_consistency",),
        resource_ids=("workflow_state_bundle", "production_state_bundle", "compiled_deck_output"),
        tool_ids=("deck_qa_audit",),
    ),
    PipelineStage.RENDER_LOCAL_PPTX: WorkflowStageBoundary(
        stage=PipelineStage.RENDER_LOCAL_PPTX,
        orchestration_role="Assemble and validate the final local PPTX from deterministic compile inputs only.",
        policy_owner_modules=("presentation_agent.pipeline.orchestrator", "presentation_agent.pipeline.executors"),
        skill_capability_ids=("validate_slide_geometry", "score_layout"),
        resource_ids=("workflow_state_bundle", "production_state_bundle", "compiled_deck_output"),
        tool_ids=("local_pptx_compilation", "local_render_validation"),
    ),
}


def stage_boundary(stage: PipelineStage | str) -> WorkflowStageBoundary:
    return WORKFLOW_STAGE_BOUNDARIES[coerce_stage(stage)]


def stage_tool_names(stage: PipelineStage | str) -> tuple[str, ...]:
    boundary = stage_boundary(stage)
    ordered: list[str] = []
    seen: set[str] = set()
    for tool_id in boundary.tool_ids:
        tool = TOOL_BOUNDARIES[tool_id]
        for tool_name in tool.acl_tool_names:
            if tool_name in seen:
                continue
            seen.add(tool_name)
            ordered.append(tool_name)
    return tuple(ordered)


def stage_skill_capability_ids(stage: PipelineStage | str) -> tuple[str, ...]:
    return stage_boundary(stage).skill_capability_ids


def resolved_prompt_template_paths(prompt_id: str) -> tuple[Path, ...]:
    return tuple((REPO_ROOT / relative_path).resolve() for relative_path in PROMPT_TEMPLATE_BOUNDARIES[prompt_id].template_paths)


def validate_workflow_boundary_registry() -> None:
    expected_stages = set(PIPELINE_STAGE_ORDER)
    actual_stages = set(WORKFLOW_STAGE_BOUNDARIES)
    missing_stages = expected_stages - actual_stages
    extra_stages = actual_stages - expected_stages
    if missing_stages or extra_stages:
        raise ValueError(
            f"workflow boundary registry stage coverage mismatch; missing={sorted(stage.value for stage in missing_stages)}, "
            f"extra={sorted(stage.value for stage in extra_stages)}"
        )

    for stage in PIPELINE_STAGE_ORDER:
        boundary = WORKFLOW_STAGE_BOUNDARIES[stage]
        if boundary.stage != stage:
            raise ValueError(f"stage boundary key mismatch for {stage.value}")
        for capability_id in boundary.skill_capability_ids:
            capability = SKILL_LIKE_CAPABILITIES.get(capability_id)
            if capability is None:
                raise ValueError(f"{stage.value} references unknown skill capability {capability_id!r}")
            if capability.primary_stage != stage:
                raise ValueError(
                    f"{stage.value} references skill capability {capability_id!r} with primary stage {capability.primary_stage.value}"
                )
        for resource_id in boundary.resource_ids:
            if resource_id not in RESOURCE_BOUNDARIES:
                raise ValueError(f"{stage.value} references unknown resource boundary {resource_id!r}")
        for tool_id in boundary.tool_ids:
            tool = TOOL_BOUNDARIES.get(tool_id)
            if tool is None:
                raise ValueError(f"{stage.value} references unknown tool boundary {tool_id!r}")
            if not tool.acl_tool_names:
                raise ValueError(f"tool boundary {tool_id!r} must declare at least one ACL tool name")
        for prompt_id in boundary.prompt_ids:
            if prompt_id not in PROMPT_TEMPLATE_BOUNDARIES:
                raise ValueError(f"{stage.value} references unknown prompt boundary {prompt_id!r}")

    for resource in RESOURCE_BOUNDARIES.values():
        if not resource.bound_names:
            raise ValueError(f"resource boundary {resource.resource_id!r} must declare at least one bound name")
    for prompt in PROMPT_TEMPLATE_BOUNDARIES.values():
        for template_path in resolved_prompt_template_paths(prompt.prompt_id):
            if not template_path.is_file():
                raise ValueError(f"prompt boundary {prompt.prompt_id!r} references missing template path {template_path}")


validate_workflow_boundary_registry()


__all__ = [
    "ExternalResourceBoundary",
    "ExternalToolBoundary",
    "PROMPT_TEMPLATE_BOUNDARIES",
    "PromptTemplateBoundary",
    "RESOURCE_BOUNDARIES",
    "SKILL_LIKE_CAPABILITIES",
    "TOOL_BOUNDARIES",
    "WORKFLOW_STAGE_BOUNDARIES",
    "WorkflowStageBoundary",
    "resolved_prompt_template_paths",
    "stage_boundary",
    "stage_skill_capability_ids",
    "stage_tool_names",
    "validate_workflow_boundary_registry",
]
