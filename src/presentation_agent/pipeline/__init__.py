"""Stage-gated harness primitives for evidence-first PPT generation."""

from .invalidation import InputAssetSnapshot, determine_invalidation_stage, extract_intake_assets, fingerprint_assets
from .executors import ExecutorResult, RuntimeStageExecutor, build_stage_executors, collect_pipeline_fingerprints
from .orchestrator import ArtifactValidationError, PipelineOrchestrator, PipelineRunResult, StageRunResult, StageTransitionError
from .state_store import ArtifactEnvelope, FingerprintRecord, PipelineHistoryEntry, PipelineRunStatus, PipelineState, PipelineStateStore, SourceEvidence
from .stages import (
    ALLOWED_STAGE_STATUSES,
    APPROVAL_GATE_STAGES,
    PIPELINE_STAGE_ORDER,
    STAGE_ARTIFACT_FILENAMES,
    PipelineStage,
    coerce_stage,
    is_blocking_status,
    is_success_status,
    next_stage,
    previous_stage,
    stage_index,
    validate_stage_status,
)
from .tool_acl import STAGE_TOOL_ACL, StageToolPolicy, assert_tool_allowed, tool_allowed

__all__ = [
    "ALLOWED_STAGE_STATUSES",
    "APPROVAL_GATE_STAGES",
    "ArtifactEnvelope",
    "ArtifactValidationError",
    "ExecutorResult",
    "FingerprintRecord",
    "InputAssetSnapshot",
    "PIPELINE_STAGE_ORDER",
    "PipelineHistoryEntry",
    "PipelineOrchestrator",
    "PipelineRunResult",
    "PipelineRunStatus",
    "PipelineStage",
    "PipelineState",
    "PipelineStateStore",
    "RuntimeStageExecutor",
    "STAGE_ARTIFACT_FILENAMES",
    "STAGE_TOOL_ACL",
    "SourceEvidence",
    "StageRunResult",
    "StageToolPolicy",
    "StageTransitionError",
    "assert_tool_allowed",
    "build_stage_executors",
    "collect_pipeline_fingerprints",
    "coerce_stage",
    "determine_invalidation_stage",
    "extract_intake_assets",
    "fingerprint_assets",
    "is_blocking_status",
    "is_success_status",
    "next_stage",
    "previous_stage",
    "stage_index",
    "tool_allowed",
    "validate_stage_status",
]
