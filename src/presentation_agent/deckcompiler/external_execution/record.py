"""Hash-bound blocked records and a root-confined write-once filesystem policy."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, TypeAlias
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..identity import canonical_json_bytes, stable_id
from .contracts import (
    ARTIFACT_ID_PATTERN,
    SHA256_PATTERN,
    ExternalExecutableId,
    ExternalExecutionRequest,
    canonical_request_bytes,
    compute_request_semantic_sha256,
)


REQUEST_HASH_DOMAIN = "deckcompiler.external_execution.request.v1"
RESPONSE_HASH_DOMAIN = "deckcompiler.external_execution.response.v1"
OUTPUT_HASH_DOMAIN = "deckcompiler.external_execution.output.v1"
EXECUTION_RECORD_HASH_DOMAIN = "deckcompiler.external_execution.record.v1"
HashDomain: TypeAlias = Literal[
    "deckcompiler.external_execution.request.v1",
    "deckcompiler.external_execution.response.v1",
    "deckcompiler.external_execution.output.v1",
    "deckcompiler.external_execution.record.v1",
    "deckcompiler.external_execution.verification_report.v1",
    "deckcompiler.external_execution.acceptance.v1",
]

BLOCKED_REASON = "external_transport_disabled_contract_only"
RESPONSE_ABSENT_REASON = "transport_not_attempted"
REPO_ROOT = Path(__file__).resolve().parents[4]


class HashBinding(BaseModel):
    """Algorithm, domain, digest, and exact byte length for one byte class."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    algorithm: Literal["sha256"] = "sha256"
    hash_domain: HashDomain
    digest: str = Field(pattern=SHA256_PATTERN)
    byte_count: int = Field(ge=0)


def build_hash_binding(value: bytes, hash_domain: HashDomain) -> HashBinding:
    if type(value) is not bytes:
        raise TypeError("hash input must be exact bytes")
    return HashBinding(
        hash_domain=hash_domain,
        digest=hashlib.sha256(value).hexdigest(),
        byte_count=len(value),
    )


class InputArtifactReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    artifact_id: str = Field(pattern=ARTIFACT_ID_PATTERN)
    sha256: str = Field(pattern=SHA256_PATTERN)


class RequestArtifactReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    artifact_id: str = Field(pattern=r"^extreq_[0-9a-f]{20}$")
    relative_path: str = Field(min_length=1)
    hash: HashBinding

    @model_validator(mode="after")
    def require_request_hash_domain(self) -> "RequestArtifactReference":
        if self.hash.hash_domain != REQUEST_HASH_DOMAIN:
            raise ValueError("request artifact must use the request hash domain")
        _validate_relative_path_syntax(self.relative_path)
        return self


class ImplementationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    component: Literal["presentation_agent.deckcompiler.external_execution"] = (
        "presentation_agent.deckcompiler.external_execution"
    )
    version: Literal["1.0.0"] = "1.0.0"
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")


class ExternalOutputReference(BaseModel):
    """Future typed output reference; v1 blocked records permit zero instances."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    artifact_id: str = Field(pattern=ARTIFACT_ID_PATTERN)
    relative_path: str = Field(min_length=1)
    hash: HashBinding

    @model_validator(mode="after")
    def require_output_hash_domain(self) -> "ExternalOutputReference":
        if self.hash.hash_domain != OUTPUT_HASH_DOMAIN:
            raise ValueError("output artifact must use the output hash domain")
        _validate_relative_path_syntax(self.relative_path)
        return self


class ExternalExecutionRecord(BaseModel):
    """Attempt-bound facts for a transport blocked before invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_name: Literal["external_execution_record"] = "external_execution_record"
    schema_version: Literal["1.0.0"] = "1.0.0"
    record_id: str = Field(pattern=r"^exrec_[0-9a-f]{20}$")
    execution_id: str = Field(pattern=r"^exec_[0-9a-f]{20}$")
    request_id: str = Field(pattern=r"^extreq_[0-9a-f]{20}$")
    run_id: str = Field(pattern=r"^run_[0-9a-f]{20}$")
    external_executable_id: ExternalExecutableId
    execution_lane: Literal["contract_only"] = "contract_only"
    request_artifact: RequestArtifactReference
    request_semantic_sha256: str = Field(pattern=SHA256_PATTERN)
    response_artifact: None = None
    response_absent_reason: Literal["transport_not_attempted"] = RESPONSE_ABSENT_REASON
    response_hash: None = None
    outputs: tuple[ExternalOutputReference, ...] = Field(
        default_factory=tuple, max_length=0
    )
    status: Literal["blocked"] = "blocked"
    transport_attempted: Literal[False] = False
    transport_call_count: Literal[0] = 0
    blocked_reason: Literal["external_transport_disabled_contract_only"] = BLOCKED_REASON
    created_at: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    input_artifacts: tuple[InputArtifactReference, ...] = Field(default_factory=tuple)
    implementation_provenance: ImplementationProvenance
    record_hash: HashBinding

    @field_validator("external_executable_id", mode="before")
    @classmethod
    def reject_provider_coercion(cls, value: object) -> object:
        if type(value) is not str:
            raise ValueError("external_executable_id must be an exact string")
        return value

    @model_validator(mode="after")
    def require_blocked_record_invariants(self) -> "ExternalExecutionRecord":
        if self.record_hash.hash_domain != EXECUTION_RECORD_HASH_DOMAIN:
            raise ValueError("record_hash must use the execution-record hash domain")
        if self.implementation_provenance.source_commit != self.source_commit:
            raise ValueError("implementation provenance source commit must match record")
        if tuple(dict.fromkeys(item.artifact_id for item in self.input_artifacts)) != tuple(
            item.artifact_id for item in self.input_artifacts
        ):
            raise ValueError("input artifact IDs must be unique and ordered")
        return self


class ExecutionRecordImmutableError(FileExistsError):
    code = "DC_EXECUTION_RECORD_IMMUTABLE"

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"{self.code}: execution record already exists: {path}")


class ExecutionRecordPathError(ValueError):
    code = "DC_EXECUTION_RECORD_PATH_UNSAFE"

    def __init__(self, message: str) -> None:
        super().__init__(f"{self.code}: {message}")


class ExecutionRecordReadBackError(IOError):
    code = "DC_EXECUTION_RECORD_READBACK_MISMATCH"


_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def _validate_relative_path_syntax(relative_path: str) -> tuple[str, ...]:
    if type(relative_path) is not str or not relative_path:
        raise ExecutionRecordPathError("path must be a nonempty relative string")
    if relative_path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", relative_path):
        raise ExecutionRecordPathError("absolute, drive, UNC, and device paths are forbidden")
    if relative_path.startswith(("\\\\?\\", "\\\\.\\")) or ":" in relative_path:
        raise ExecutionRecordPathError("device paths and alternate data streams are forbidden")
    parts = tuple(part for part in re.split(r"[\\/]", relative_path) if part != "")
    if not parts or any(part in {".", ".."} for part in parts):
        raise ExecutionRecordPathError("dot segments and the run root itself are forbidden")
    for part in parts:
        base = part.rstrip(" .").split(".", 1)[0].upper()
        if base in _RESERVED_WINDOWS_NAMES:
            raise ExecutionRecordPathError("reserved Windows device names are forbidden")
    return parts


def _is_reparse_point(path: Path) -> bool:
    try:
        status = os.lstat(path)
    except FileNotFoundError:
        return False
    attributes = getattr(status, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_approved_path(
    run_root: str | Path,
    relative_path: str,
    *,
    must_exist: bool,
) -> Path:
    """Resolve one path under a non-repository run root without following reparse hops."""

    root = Path(run_root)
    if not root.exists() or not root.is_dir():
        raise ExecutionRecordPathError("approved run root must be an existing directory")
    root_resolved = root.resolve(strict=True)
    repo_resolved = REPO_ROOT.resolve(strict=True)
    if _is_within(root_resolved, repo_resolved):
        raise ExecutionRecordPathError("approved run root must be outside the repository")
    if _is_reparse_point(root):
        raise ExecutionRecordPathError("approved run root cannot be a symlink or reparse point")

    parts = _validate_relative_path_syntax(relative_path)
    current = root
    for part in parts[:-1]:
        current = current / part
        if not current.exists() or not current.is_dir():
            raise ExecutionRecordPathError("record parent directories must already exist")
        if _is_reparse_point(current):
            raise ExecutionRecordPathError("parent symlink or reparse point is forbidden")

    target = root.joinpath(*parts)
    if target.exists() and _is_reparse_point(target):
        raise ExecutionRecordPathError("target symlink or reparse point is forbidden")
    resolved = target.resolve(strict=must_exist)
    if not _is_within(resolved, root_resolved) or resolved == root_resolved:
        raise ExecutionRecordPathError("path escapes or equals the approved run root")
    if must_exist and not target.is_file():
        raise ExecutionRecordPathError("expected artifact must be an existing regular file")
    if not must_exist and target.exists() and target.is_dir():
        raise ExecutionRecordPathError("record target cannot be a directory")
    return target


def compute_execution_record_hash(
    record: ExternalExecutionRecord | Mapping[str, Any],
) -> HashBinding:
    payload = (
        record.model_dump(mode="json")
        if isinstance(record, ExternalExecutionRecord)
        else dict(record)
    )
    payload.pop("record_hash", None)
    return build_hash_binding(
        canonical_json_bytes(payload),
        EXECUTION_RECORD_HASH_DOMAIN,
    )


def canonical_execution_record_bytes(record: ExternalExecutionRecord) -> bytes:
    return canonical_json_bytes(record.model_dump(mode="json"))


def build_blocked_execution_record(
    request: ExternalExecutionRequest,
    *,
    request_artifact_path: str,
    request_bytes: bytes,
    created_at: str,
) -> ExternalExecutionRecord:
    if request_bytes != canonical_request_bytes(request):
        raise ValueError("request_bytes must be the canonical bytes of request")
    input_artifacts = tuple(
        InputArtifactReference(artifact_id=item.artifact_id, sha256=item.sha256)
        for item in request.references
    )
    if tuple(item.artifact_id for item in input_artifacts) != request.upstream_artifact_ids:
        raise ValueError("every upstream artifact ID must resolve to a hashed input reference")
    request_hash = build_hash_binding(request_bytes, REQUEST_HASH_DOMAIN)
    payload: dict[str, Any] = {
        "schema_name": "external_execution_record",
        "schema_version": "1.0.0",
        "record_id": stable_id(
            "exrec",
            request.execution_id,
            request.external_executable_id,
            request_hash.digest,
            BLOCKED_REASON,
        ),
        "execution_id": request.execution_id,
        "request_id": request.request_id,
        "run_id": request.run_id,
        "external_executable_id": request.external_executable_id,
        "execution_lane": "contract_only",
        "request_artifact": {
            "artifact_id": request.request_id,
            "relative_path": request_artifact_path,
            "hash": request_hash.model_dump(mode="json"),
        },
        "request_semantic_sha256": compute_request_semantic_sha256(request),
        "response_artifact": None,
        "response_absent_reason": RESPONSE_ABSENT_REASON,
        "response_hash": None,
        "outputs": (),
        "status": "blocked",
        "transport_attempted": False,
        "transport_call_count": 0,
        "blocked_reason": BLOCKED_REASON,
        "created_at": created_at,
        "source_commit": request.source_commit,
        "input_artifacts": tuple(
            item.model_dump(mode="json") for item in input_artifacts
        ),
        "implementation_provenance": {
            "component": "presentation_agent.deckcompiler.external_execution",
            "version": "1.0.0",
            "source_commit": request.source_commit,
        },
    }
    payload["record_hash"] = compute_execution_record_hash(payload).model_dump(
        mode="json"
    )
    return ExternalExecutionRecord.model_validate(payload)


def write_execution_record(
    run_root: str | Path,
    relative_path: str,
    record: ExternalExecutionRecord,
) -> Path:
    """Install canonical bytes without overwrite, then independently read them back."""

    target = resolve_approved_path(run_root, relative_path, must_exist=False)
    if target.exists() or target.is_symlink():
        if target.is_dir():
            raise ExecutionRecordPathError("record target cannot be a directory")
        raise ExecutionRecordImmutableError(target)

    expected_bytes = canonical_execution_record_bytes(record)
    temp = target.parent / f".{target.name}.{uuid4().hex}.tmp"
    linked = False
    try:
        with temp.open("xb") as stream:
            stream.write(expected_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, target, follow_symlinks=False)
        linked = True
        temp.unlink()
        actual_bytes = target.read_bytes()
        if actual_bytes != expected_bytes:
            raise ExecutionRecordReadBackError(
                "execution record bytes changed during write/read-back verification"
            )
        if compute_execution_record_hash(record) != record.record_hash:
            raise ExecutionRecordReadBackError("execution record hash is not self-consistent")
    except FileExistsError as exc:
        raise ExecutionRecordImmutableError(target) from exc
    except Exception:
        temp.unlink(missing_ok=True)
        if linked:
            target.unlink(missing_ok=True)
        raise
    return target


__all__ = [
    "BLOCKED_REASON",
    "EXECUTION_RECORD_HASH_DOMAIN",
    "ExecutionRecordImmutableError",
    "ExecutionRecordPathError",
    "ExecutionRecordReadBackError",
    "ExternalExecutionRecord",
    "ExternalOutputReference",
    "HashBinding",
    "ImplementationProvenance",
    "InputArtifactReference",
    "OUTPUT_HASH_DOMAIN",
    "RESPONSE_ABSENT_REASON",
    "RESPONSE_HASH_DOMAIN",
    "REQUEST_HASH_DOMAIN",
    "RequestArtifactReference",
    "build_blocked_execution_record",
    "build_hash_binding",
    "canonical_execution_record_bytes",
    "canonical_json_bytes",
    "compute_execution_record_hash",
    "resolve_approved_path",
    "write_execution_record",
]
