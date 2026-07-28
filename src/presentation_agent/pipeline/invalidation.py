"""Input fingerprinting and downstream invalidation helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .state_store import ArtifactEnvelope, FingerprintRecord
from .stages import PipelineStage, stage_index


class InputAssetSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    asset_id: str
    filename: str
    roles: list[str] = Field(default_factory=list)
    fingerprint: str | None = None

    @field_validator("roles", mode="before")
    @classmethod
    def _coerce_roles(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item).strip() for item in value if str(item).strip()]

    def normalized_payload(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "filename": self.filename,
            "roles": sorted({role for role in self.roles if role}),
            "fingerprint": self.fingerprint or "",
        }


REQUEST_CONTRACT_ROLES = frozenset({"output_requirement", "supplemental_context", "request_contract", "prompt_set_version", "schema_version"})
CONTENT_ROLES = frozenset({"content_source", "master_template_artifact"})
DESIGN_ROLES = frozenset({"design_reference", "brand_constraint"})
RENDERER_ROLES = frozenset({"renderer_version"})


def fingerprint_assets(assets: list[InputAssetSnapshot]) -> str:
    normalized = [asset.normalized_payload() for asset in sorted(assets, key=lambda item: item.asset_id)]
    encoded = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def fingerprint_path(path: str | Path) -> str:
    resolved = Path(path)
    digest = hashlib.sha256()
    if resolved.is_dir():
        for candidate in sorted(item for item in resolved.rglob("*") if item.is_file()):
            digest.update(str(candidate.relative_to(resolved)).replace("\\", "/").encode("utf-8"))
            digest.update(candidate.read_bytes())
        return digest.hexdigest()
    digest.update(resolved.read_bytes())
    return digest.hexdigest()


def fingerprint_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def extract_intake_assets(artifact: ArtifactEnvelope | None) -> list[InputAssetSnapshot]:
    if artifact is None:
        return []
    extras = artifact.model_extra or {}
    raw_assets = extras.get("assets")
    if not isinstance(raw_assets, list):
        return []
    return [InputAssetSnapshot.model_validate(item) for item in raw_assets]


def determine_invalidation_stage(
    previous_assets: list[InputAssetSnapshot],
    current_assets: list[InputAssetSnapshot],
) -> PipelineStage | None:
    previous_map = {asset.asset_id: asset.normalized_payload() for asset in previous_assets}
    current_map = {asset.asset_id: asset.normalized_payload() for asset in current_assets}
    if previous_map == current_map:
        return None

    earliest: PipelineStage | None = None
    all_asset_ids = sorted(set(previous_map) | set(current_map))
    for asset_id in all_asset_ids:
        before = previous_map.get(asset_id)
        after = current_map.get(asset_id)
        if before == after:
            continue
        roles = set()
        if before is not None:
            roles.update(before.get("roles", []))
        if after is not None:
            roles.update(after.get("roles", []))
        candidate = _stage_for_roles(roles)
        if earliest is None or stage_index(candidate) < stage_index(earliest):
            earliest = candidate
    return earliest or PipelineStage.INGEST


def determine_invalidation_stage_from_fingerprints(
    previous_records: list[FingerprintRecord],
    current_records: list[FingerprintRecord],
) -> PipelineStage | None:
    previous_map = {record.key: record for record in previous_records}
    current_map = {record.key: record for record in current_records}
    if previous_map.keys() == current_map.keys() and all(
        previous_map[key].digest == current_map[key].digest and previous_map[key].invalidates_from_stage == current_map[key].invalidates_from_stage
        for key in previous_map
    ):
        return None

    earliest: PipelineStage | None = None
    for key in sorted(set(previous_map) | set(current_map)):
        previous_record = previous_map.get(key)
        current_record = current_map.get(key)
        if previous_record is not None and current_record is not None:
            if previous_record.digest == current_record.digest and previous_record.invalidates_from_stage == current_record.invalidates_from_stage:
                continue
        candidate = (
            current_record.invalidates_from_stage
            if current_record is not None
            else previous_record.invalidates_from_stage if previous_record is not None else PipelineStage.INGEST
        )
        if earliest is None or stage_index(candidate) < stage_index(earliest):
            earliest = candidate
    return earliest


def _stage_for_roles(roles: set[str]) -> PipelineStage:
    if roles & REQUEST_CONTRACT_ROLES:
        return PipelineStage.INGEST
    if roles & CONTENT_ROLES:
        return PipelineStage.CONTENT_PLAN
    if roles & DESIGN_ROLES:
        return PipelineStage.DESIGN_REFERENCE_CHECK
    if roles & RENDERER_ROLES:
        return PipelineStage.RENDER_LOCAL_PPTX
    return PipelineStage.INGEST
