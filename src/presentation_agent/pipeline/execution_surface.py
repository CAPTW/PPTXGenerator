"""Alignment layer between harness stages and the legacy-backed runtime surface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..non_pptx_modules.runtime_config import RuntimePipelineConfig
from ..non_pptx_modules.runtime_pipeline import (
    LEGACY_RUNTIME_STAGE_ORDER,
    RuntimeWorkspace,
    StageExecution,
    legacy_stage_artifacts,
    run_stage,
)
from .gate_policy import DEFAULT_GATE_APPROVAL_POLICY
from .stages import PIPELINE_STAGE_ORDER, PipelineStage, coerce_stage


@dataclass(frozen=True, slots=True)
class ActiveExecutionSurface:
    stage: PipelineStage
    summary: str
    runtime_stage_sequence: tuple[str, ...] = ()

    @property
    def requires_blueprint_approved(self) -> bool:
        return DEFAULT_GATE_APPROVAL_POLICY.blueprint_policy_for(self.stage).requires_blueprint_approved

    def expected_runtime_artifacts(self, workspace: RuntimeWorkspace) -> tuple[Path, ...]:
        seen: set[Path] = set()
        ordered: list[Path] = []
        for runtime_stage in self.runtime_stage_sequence:
            for path in legacy_stage_artifacts(runtime_stage, workspace):
                if path in seen:
                    continue
                seen.add(path)
                ordered.append(path)
        return tuple(ordered)


ACTIVE_EXECUTION_SURFACES: dict[PipelineStage, ActiveExecutionSurface] = {
    PipelineStage.INGEST: ActiveExecutionSurface(
        stage=PipelineStage.INGEST,
        summary="Harness-owned ingest, classification, and fingerprint refresh.",
    ),
    PipelineStage.DESIGN_REFERENCE_CHECK: ActiveExecutionSurface(
        stage=PipelineStage.DESIGN_REFERENCE_CHECK,
        summary="Workflow planning plus reference/style grounding before template approval.",
        runtime_stage_sequence=("gate1-plan",),
    ),
    PipelineStage.MASTER_TEMPLATE: ActiveExecutionSurface(
        stage=PipelineStage.MASTER_TEMPLATE,
        summary="Harness-owned template bundle freeze after design-reference approval.",
    ),
    PipelineStage.CONTENT_PLAN: ActiveExecutionSurface(
        stage=PipelineStage.CONTENT_PLAN,
        summary="Gate 2 blueprint/design-system planning through the legacy-backed runtime adapter.",
        runtime_stage_sequence=("gate2-blueprint",),
    ),
    PipelineStage.GENERATE: ActiveExecutionSurface(
        stage=PipelineStage.GENERATE,
        summary="Deterministic asset derivation, crop extraction/review, and structured visual rendering.",
        runtime_stage_sequence=("derive-assets", "extract-assets", "review-crops", "render-visuals"),
    ),
    PipelineStage.QA: ActiveExecutionSurface(
        stage=PipelineStage.QA,
        summary="Preflight compile, deterministic QA, and large-deck orchestration.",
        runtime_stage_sequence=("compile-pptx", "qa-deck", "orchestrate-large-deck"),
    ),
    PipelineStage.RENDER_LOCAL_PPTX: ActiveExecutionSurface(
        stage=PipelineStage.RENDER_LOCAL_PPTX,
        summary="Final local compile availability plus render validation metadata.",
        runtime_stage_sequence=("compile-pptx",),
    ),
}


@dataclass(slots=True)
class AlignedRuntimeExecutionSurface:
    config: RuntimePipelineConfig
    workspace: RuntimeWorkspace

    def effective_config_for(self, stage: PipelineStage | str) -> RuntimePipelineConfig:
        return DEFAULT_GATE_APPROVAL_POLICY.effective_runtime_config(self.config, stage)

    def execute(self, stage: PipelineStage | str, *, force: bool = False) -> tuple[StageExecution, ...]:
        surface = stage_execution_surface(stage)
        config = self.effective_config_for(surface.stage)
        return tuple(run_stage(runtime_stage, config, self.workspace, force=force) for runtime_stage in surface.runtime_stage_sequence)

    def execute_single(self, stage: PipelineStage | str, *, force: bool = False) -> StageExecution:
        results = self.execute(stage, force=force)
        if len(results) != 1:
            normalized_stage = stage_execution_surface(stage).stage
            raise ValueError(
                f"{normalized_stage.value} maps to {len(results)} runtime stages; expected exactly one"
            )
        return results[0]


def stage_execution_surface(stage: PipelineStage | str) -> ActiveExecutionSurface:
    return ACTIVE_EXECUTION_SURFACES[coerce_stage(stage)]


def build_aligned_runtime_execution_surface(
    config: RuntimePipelineConfig,
    workspace: RuntimeWorkspace,
) -> AlignedRuntimeExecutionSurface:
    return AlignedRuntimeExecutionSurface(config=config, workspace=workspace)


def validate_execution_surface_alignment() -> None:
    expected_stages = set(PIPELINE_STAGE_ORDER)
    actual_stages = set(ACTIVE_EXECUTION_SURFACES)
    missing_stages = expected_stages - actual_stages
    extra_stages = actual_stages - expected_stages
    if missing_stages or extra_stages:
        raise ValueError(
            f"execution surface coverage mismatch; missing={sorted(stage.value for stage in missing_stages)}, "
            f"extra={sorted(stage.value for stage in extra_stages)}"
        )

    legacy_stage_names = set(LEGACY_RUNTIME_STAGE_ORDER)
    unknown_runtime_stages = sorted(
        runtime_stage
        for surface in ACTIVE_EXECUTION_SURFACES.values()
        for runtime_stage in surface.runtime_stage_sequence
        if runtime_stage not in legacy_stage_names
    )
    if unknown_runtime_stages:
        raise ValueError(
            "execution surface references unknown legacy runtime stages: " + ", ".join(unknown_runtime_stages)
        )


__all__ = [
    "ACTIVE_EXECUTION_SURFACES",
    "ActiveExecutionSurface",
    "AlignedRuntimeExecutionSurface",
    "build_aligned_runtime_execution_surface",
    "stage_execution_surface",
    "validate_execution_surface_alignment",
]
