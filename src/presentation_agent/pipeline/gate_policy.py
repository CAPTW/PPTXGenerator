"""Gate-state views and approval policy helpers for the stage-gated harness."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..non_pptx_modules.runtime_config import RuntimePipelineConfig
from .stages import (
    ALLOWED_STAGE_STATUSES,
    SUCCESS_STAGE_STATUSES,
    PipelineStage,
    coerce_stage,
    next_stage,
    stage_index,
    validate_stage_status,
)
from .state_store import PipelineRunStatus, PipelineState


class ApprovalEvidenceSource(StrEnum):
    REPO_BACKED = "repo-backed"
    OPERATOR_ENFORCED = "operator-enforced"


@dataclass(frozen=True, slots=True)
class StageStatusPolicy:
    stage: PipelineStage
    success_statuses: frozenset[str]
    blocking_statuses: frozenset[str]


@dataclass(frozen=True, slots=True)
class BlueprintApprovalPolicy:
    stage: PipelineStage
    requires_blueprint_approved: bool
    evidence_source: ApprovalEvidenceSource
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GateStateSnapshot:
    current_stage: PipelineStage
    run_status: PipelineRunStatus
    invalidated_from_stage: PipelineStage | None
    approved_stages: tuple[PipelineStage, ...]

    @classmethod
    def from_state(cls, state: PipelineState) -> GateStateSnapshot:
        approved_stage_list: list[PipelineStage] = []
        for stage in state.approved_artifacts:
            if not str(stage).strip():
                continue
            try:
                approved_stage_list.append(coerce_stage(stage))
            except ValueError:
                continue
        approved_stages = tuple(sorted(approved_stage_list, key=stage_index))
        return cls(
            current_stage=state.current_stage,
            run_status=state.status,
            invalidated_from_stage=state.invalidated_from_stage,
            approved_stages=approved_stages,
        )


@dataclass(frozen=True, slots=True)
class ExecutorGateOutcome:
    stage: PipelineStage
    status: str
    next_stage: PipelineStage | None


@dataclass(frozen=True, slots=True)
class GateTransition:
    stage: PipelineStage
    status: str
    approved: bool
    resulting_stage: PipelineStage
    run_status: PipelineRunStatus


STAGE_STATUS_POLICIES: dict[PipelineStage, StageStatusPolicy] = {
    stage: StageStatusPolicy(
        stage=stage,
        success_statuses=SUCCESS_STAGE_STATUSES[stage],
        blocking_statuses=frozenset(ALLOWED_STAGE_STATUSES[stage] - SUCCESS_STAGE_STATUSES[stage]),
    )
    for stage in PipelineStage
}


BLUEPRINT_APPROVAL_POLICIES: dict[PipelineStage, BlueprintApprovalPolicy] = {
    PipelineStage.INGEST: BlueprintApprovalPolicy(
        stage=PipelineStage.INGEST,
        requires_blueprint_approved=False,
        evidence_source=ApprovalEvidenceSource.REPO_BACKED,
        notes=("No blueprint approval representation is needed before Gate 2 planning exists.",),
    ),
    PipelineStage.DESIGN_REFERENCE_CHECK: BlueprintApprovalPolicy(
        stage=PipelineStage.DESIGN_REFERENCE_CHECK,
        requires_blueprint_approved=False,
        evidence_source=ApprovalEvidenceSource.REPO_BACKED,
        notes=("Design-reference planning does not mint blueprint approval state.",),
    ),
    PipelineStage.MASTER_TEMPLATE: BlueprintApprovalPolicy(
        stage=PipelineStage.MASTER_TEMPLATE,
        requires_blueprint_approved=False,
        evidence_source=ApprovalEvidenceSource.REPO_BACKED,
        notes=("Template freeze consumes prior approval artifacts without forcing runtime config changes.",),
    ),
    PipelineStage.CONTENT_PLAN: BlueprintApprovalPolicy(
        stage=PipelineStage.CONTENT_PLAN,
        requires_blueprint_approved=True,
        evidence_source=ApprovalEvidenceSource.OPERATOR_ENFORCED,
        notes=("Legacy Gate 2 output still needs blueprint approval represented in emitted state.",),
    ),
    PipelineStage.GENERATE: BlueprintApprovalPolicy(
        stage=PipelineStage.GENERATE,
        requires_blueprint_approved=False,
        evidence_source=ApprovalEvidenceSource.REPO_BACKED,
        notes=("Generation consumes persisted planning artifacts and does not mutate approval representation.",),
    ),
    PipelineStage.QA: BlueprintApprovalPolicy(
        stage=PipelineStage.QA,
        requires_blueprint_approved=True,
        evidence_source=ApprovalEvidenceSource.OPERATOR_ENFORCED,
        notes=("Legacy compile and QA helpers still require blueprint_approved=true in runtime config.",),
    ),
    PipelineStage.RENDER_LOCAL_PPTX: BlueprintApprovalPolicy(
        stage=PipelineStage.RENDER_LOCAL_PPTX,
        requires_blueprint_approved=True,
        evidence_source=ApprovalEvidenceSource.OPERATOR_ENFORCED,
        notes=("Final legacy compile availability still depends on blueprint_approved=true in runtime config.",),
    ),
}


class GateApprovalPolicy:
    def status_policy_for(self, stage: PipelineStage | str) -> StageStatusPolicy:
        return STAGE_STATUS_POLICIES[coerce_stage(stage)]

    def blueprint_policy_for(self, stage: PipelineStage | str) -> BlueprintApprovalPolicy:
        return BLUEPRINT_APPROVAL_POLICIES[coerce_stage(stage)]

    def validate_status(self, stage: PipelineStage | str, status: str) -> str:
        return validate_stage_status(stage, status)

    def is_success(self, stage: PipelineStage | str, status: str) -> bool:
        normalized_stage = coerce_stage(stage)
        normalized_status = self.validate_status(normalized_stage, status)
        return normalized_status in self.status_policy_for(normalized_stage).success_statuses

    def is_blocking(self, stage: PipelineStage | str, status: str) -> bool:
        return not self.is_success(stage, status)

    def success_status(self, stage: PipelineStage | str) -> str:
        normalized_stage = coerce_stage(stage)
        success_statuses = self.status_policy_for(normalized_stage).success_statuses
        if len(success_statuses) != 1:
            raise ValueError(f"{normalized_stage.value} has multiple success statuses; choose one explicitly.")
        return next(iter(success_statuses))

    def blocking_status(self, stage: PipelineStage | str) -> str:
        normalized_stage = coerce_stage(stage)
        blocking_statuses = self.status_policy_for(normalized_stage).blocking_statuses
        if len(blocking_statuses) != 1:
            raise ValueError(f"{normalized_stage.value} has multiple blocking statuses; choose one explicitly.")
        return next(iter(blocking_statuses))

    def approved_transition(self, stage: PipelineStage | str, status: str | None = None) -> GateTransition:
        normalized_stage = coerce_stage(stage)
        normalized_status = self.success_status(normalized_stage) if status is None else self.validate_status(normalized_stage, status)
        next_legal_stage = next_stage(normalized_stage)
        if next_legal_stage is None:
            return GateTransition(
                stage=normalized_stage,
                status=normalized_status,
                approved=True,
                resulting_stage=normalized_stage,
                run_status=PipelineRunStatus.COMPLETE,
            )
        return GateTransition(
            stage=normalized_stage,
            status=normalized_status,
            approved=True,
            resulting_stage=next_legal_stage,
            run_status=PipelineRunStatus.RUNNING,
        )

    def blocked_transition(
        self,
        stage: PipelineStage | str,
        *,
        rollback_stage: PipelineStage | str,
        status: str,
    ) -> GateTransition:
        normalized_stage = coerce_stage(stage)
        normalized_status = self.validate_status(normalized_stage, status)
        if not self.is_blocking(normalized_stage, normalized_status):
            raise ValueError(f"{normalized_stage.value} status {normalized_status!r} is not blocking.")
        return GateTransition(
            stage=normalized_stage,
            status=normalized_status,
            approved=False,
            resulting_stage=coerce_stage(rollback_stage),
            run_status=PipelineRunStatus.BLOCKED,
        )

    def qa_executor_outcome(self, qa_status: str) -> ExecutorGateOutcome:
        normalized = str(qa_status).strip().lower()
        if normalized == "pass":
            return ExecutorGateOutcome(stage=PipelineStage.QA, status="PASS", next_stage=None)
        if normalized == "conditional-pass":
            return ExecutorGateOutcome(stage=PipelineStage.QA, status="REPAIRABLE_FAIL", next_stage=PipelineStage.GENERATE)
        return ExecutorGateOutcome(stage=PipelineStage.QA, status="FAIL", next_stage=PipelineStage.GENERATE)

    def render_executor_outcome(self, *, failed: bool) -> ExecutorGateOutcome:
        status = "FAIL" if failed else "SUCCESS"
        next_retry_stage = PipelineStage.RENDER_LOCAL_PPTX if failed else None
        return ExecutorGateOutcome(
            stage=PipelineStage.RENDER_LOCAL_PPTX,
            status=status,
            next_stage=next_retry_stage,
        )

    def effective_runtime_config(self, config: RuntimePipelineConfig, stage: PipelineStage | str) -> RuntimePipelineConfig:
        approval_policy = self.blueprint_policy_for(stage)
        if not approval_policy.requires_blueprint_approved or config.blueprint_approved:
            return config
        return config.model_copy(update={"blueprint_approved": True})


DEFAULT_GATE_APPROVAL_POLICY = GateApprovalPolicy()


__all__ = [
    "ApprovalEvidenceSource",
    "BLUEPRINT_APPROVAL_POLICIES",
    "BlueprintApprovalPolicy",
    "DEFAULT_GATE_APPROVAL_POLICY",
    "ExecutorGateOutcome",
    "GateApprovalPolicy",
    "GateStateSnapshot",
    "GateTransition",
    "STAGE_STATUS_POLICIES",
    "StageStatusPolicy",
]
