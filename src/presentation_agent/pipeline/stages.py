"""Stage definitions for the stage-gated presentation harness."""

from __future__ import annotations

from enum import StrEnum


class PipelineStage(StrEnum):
    INGEST = "INGEST"
    DESIGN_REFERENCE_CHECK = "DESIGN_REFERENCE_CHECK"
    MASTER_TEMPLATE = "MASTER_TEMPLATE"
    CONTENT_PLAN = "CONTENT_PLAN"
    GENERATE = "GENERATE"
    QA = "QA"
    RENDER_LOCAL_PPTX = "RENDER_LOCAL_PPTX"


PIPELINE_STAGE_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.INGEST,
    PipelineStage.DESIGN_REFERENCE_CHECK,
    PipelineStage.MASTER_TEMPLATE,
    PipelineStage.CONTENT_PLAN,
    PipelineStage.GENERATE,
    PipelineStage.QA,
    PipelineStage.RENDER_LOCAL_PPTX,
)

STAGE_ARTIFACT_FILENAMES: dict[PipelineStage, str] = {
    PipelineStage.INGEST: "intake_manifest.json",
    PipelineStage.DESIGN_REFERENCE_CHECK: "design_reference_report.json",
    PipelineStage.MASTER_TEMPLATE: "master_template.json",
    PipelineStage.CONTENT_PLAN: "content_plan.json",
    PipelineStage.GENERATE: "generation_manifest.json",
    PipelineStage.QA: "qa_report.json",
    PipelineStage.RENDER_LOCAL_PPTX: "render_report.json",
}

ALLOWED_STAGE_STATUSES: dict[PipelineStage, frozenset[str]] = {
    PipelineStage.INGEST: frozenset({"APPROVED", "BLOCKED"}),
    PipelineStage.DESIGN_REFERENCE_CHECK: frozenset({"APPROVED", "INSUFFICIENT", "BLOCKED"}),
    PipelineStage.MASTER_TEMPLATE: frozenset({"APPROVED", "BLOCKED"}),
    PipelineStage.CONTENT_PLAN: frozenset({"APPROVED", "BLOCKED"}),
    PipelineStage.GENERATE: frozenset({"APPROVED", "BLOCKED"}),
    PipelineStage.QA: frozenset({"PASS", "FAIL", "REPAIRABLE_FAIL"}),
    PipelineStage.RENDER_LOCAL_PPTX: frozenset({"SUCCESS", "FAIL"}),
}

SUCCESS_STAGE_STATUSES: dict[PipelineStage, frozenset[str]] = {
    PipelineStage.INGEST: frozenset({"APPROVED"}),
    PipelineStage.DESIGN_REFERENCE_CHECK: frozenset({"APPROVED"}),
    PipelineStage.MASTER_TEMPLATE: frozenset({"APPROVED"}),
    PipelineStage.CONTENT_PLAN: frozenset({"APPROVED"}),
    PipelineStage.GENERATE: frozenset({"APPROVED"}),
    PipelineStage.QA: frozenset({"PASS"}),
    PipelineStage.RENDER_LOCAL_PPTX: frozenset({"SUCCESS"}),
}

APPROVAL_GATE_STAGES = frozenset(
    {
        PipelineStage.DESIGN_REFERENCE_CHECK,
        PipelineStage.MASTER_TEMPLATE,
        PipelineStage.QA,
    }
)


def coerce_stage(value: PipelineStage | str) -> PipelineStage:
    if isinstance(value, PipelineStage):
        return value
    return PipelineStage(str(value).strip().upper())


def stage_index(stage: PipelineStage | str) -> int:
    return PIPELINE_STAGE_ORDER.index(coerce_stage(stage))


def previous_stage(stage: PipelineStage | str) -> PipelineStage | None:
    index = stage_index(stage)
    if index == 0:
        return None
    return PIPELINE_STAGE_ORDER[index - 1]


def next_stage(stage: PipelineStage | str) -> PipelineStage | None:
    index = stage_index(stage)
    if index == len(PIPELINE_STAGE_ORDER) - 1:
        return None
    return PIPELINE_STAGE_ORDER[index + 1]


def validate_stage_status(stage: PipelineStage | str, status: str) -> str:
    normalized_stage = coerce_stage(stage)
    normalized_status = status.strip().upper()
    allowed = ALLOWED_STAGE_STATUSES[normalized_stage]
    if normalized_status not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(f"status {normalized_status!r} is not valid for stage {normalized_stage.value}; expected one of {allowed_text}")
    return normalized_status


def is_success_status(stage: PipelineStage | str, status: str) -> bool:
    normalized_stage = coerce_stage(stage)
    normalized_status = validate_stage_status(normalized_stage, status)
    return normalized_status in SUCCESS_STAGE_STATUSES[normalized_stage]


def is_blocking_status(stage: PipelineStage | str, status: str) -> bool:
    return not is_success_status(stage, status)
