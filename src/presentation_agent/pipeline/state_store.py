"""Persistent state and artifact storage for the stage-gated harness."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .stages import PIPELINE_STAGE_ORDER, STAGE_ARTIFACT_FILENAMES, PipelineStage, coerce_stage, stage_index, validate_stage_status


class SourceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset_id: str | None = None
    artifact: str | None = None
    reason: str

    @model_validator(mode="after")
    def _validate_source(self) -> "SourceEvidence":
        if not self.asset_id and not self.artifact:
            raise ValueError("source evidence requires either asset_id or artifact")
        return self


class FingerprintRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    key: str
    digest: str
    invalidates_from_stage: PipelineStage
    sources: list[str] = Field(default_factory=list)

    @field_validator("invalidates_from_stage", mode="before")
    @classmethod
    def _coerce_stage(cls, value: PipelineStage | str) -> PipelineStage:
        return coerce_stage(value)


class ArtifactEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True, validate_assignment=True)

    stage: PipelineStage
    status: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    invalidates_downstream_from: PipelineStage | None = None

    @field_validator("stage", mode="before")
    @classmethod
    def _coerce_stage(cls, value: PipelineStage | str) -> PipelineStage:
        return coerce_stage(value)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str, info) -> str:
        stage = info.data.get("stage")
        if stage is None:
            return value.strip().upper()
        return validate_stage_status(stage, value)

    @field_validator("invalidates_downstream_from", mode="before")
    @classmethod
    def _coerce_invalidates_stage(cls, value: PipelineStage | str | None) -> PipelineStage | None:
        if value is None:
            return None
        return coerce_stage(value)


class PipelineHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    stage: PipelineStage
    status: str
    artifact: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("stage", mode="before")
    @classmethod
    def _coerce_stage(cls, value: PipelineStage | str) -> PipelineStage:
        return coerce_stage(value)


class PipelineRunStatus(StrEnum):
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    COMPLETE = "COMPLETE"


class PipelineState(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    current_stage: PipelineStage = PipelineStage.INGEST
    status: PipelineRunStatus = PipelineRunStatus.RUNNING
    approved_artifacts: dict[str, str] = Field(default_factory=dict)
    invalidated_from_stage: PipelineStage | None = None
    last_input_fingerprint: str | None = None
    fingerprints: list[FingerprintRecord] = Field(default_factory=list)
    history: list[PipelineHistoryEntry] = Field(default_factory=list)

    @field_validator("current_stage", "invalidated_from_stage", mode="before")
    @classmethod
    def _coerce_stage(cls, value: PipelineStage | str | None) -> PipelineStage | None:
        if value is None:
            return None
        return coerce_stage(value)


class PipelineStateStore:
    """Filesystem-backed store for harness state and artifacts."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def pipeline_state_path(self) -> Path:
        return self.root / "pipeline_state.json"

    def artifact_path(self, stage: PipelineStage | str) -> Path:
        return self.root / STAGE_ARTIFACT_FILENAMES[coerce_stage(stage)]

    def load_pipeline_state(self) -> PipelineState:
        if not self.pipeline_state_path.is_file():
            return PipelineState()
        return PipelineState.model_validate_json(self.pipeline_state_path.read_text(encoding="utf-8"))

    def save_pipeline_state(self, state: PipelineState) -> Path:
        return self._write_model(self.pipeline_state_path, state)

    def load_artifact(self, stage: PipelineStage | str) -> ArtifactEnvelope | None:
        path = self.artifact_path(stage)
        if not path.is_file():
            return None
        return ArtifactEnvelope.model_validate_json(path.read_text(encoding="utf-8"))

    def save_artifact(self, artifact: ArtifactEnvelope) -> Path:
        return self._write_model(self.artifact_path(artifact.stage), artifact)

    def delete_artifact(self, stage: PipelineStage | str) -> None:
        path = self.artifact_path(stage)
        if path.exists():
            path.unlink()

    def invalidate_from(
        self,
        stage: PipelineStage | str,
        *,
        state: PipelineState | None = None,
        last_input_fingerprint: str | None = None,
    ) -> PipelineState:
        normalized_stage = coerce_stage(stage)
        for candidate in PIPELINE_STAGE_ORDER:
            if stage_index(candidate) >= stage_index(normalized_stage):
                self.delete_artifact(candidate)
        current_state = state or self.load_pipeline_state()
        current_state.current_stage = normalized_stage
        current_state.status = PipelineRunStatus.RUNNING
        current_state.invalidated_from_stage = normalized_stage
        if last_input_fingerprint is not None:
            current_state.last_input_fingerprint = last_input_fingerprint
        current_state.approved_artifacts = self._filter_approved_artifacts_before(normalized_stage, current_state.approved_artifacts)
        self.save_pipeline_state(current_state)
        return current_state

    def _filter_approved_artifacts_before(self, stage: PipelineStage, approved: dict[str, str]) -> dict[str, str]:
        filtered: dict[str, str] = {}
        for key, value in approved.items():
            try:
                approved_stage = coerce_stage(key)
            except ValueError:
                continue
            if stage_index(approved_stage) < stage_index(stage):
                filtered[approved_stage.value] = value
        return filtered

    def _write_model(self, path: Path, model: BaseModel) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = model.model_dump(mode="json", exclude_none=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
