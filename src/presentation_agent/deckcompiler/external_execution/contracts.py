"""Typed, immutable contracts for the fail-closed external-execution lane."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..identity import canonical_json_bytes, content_sha256, stable_id

if TYPE_CHECKING:
    from .record import ExternalExecutionRecord


ExternalExecutableId: TypeAlias = Literal[
    "openai",
    "openai_api",
    "scout_assist",
    "scout_suggestions",
]

# This tuple is the single runtime authorization source. Schema parity is enforced
# by tests; callers must not normalize or alias values before membership checking.
APPROVED_EXTERNAL_EXECUTABLE_IDS: tuple[ExternalExecutableId, ...] = (
    "openai",
    "openai_api",
    "scout_assist",
    "scout_suggestions",
)

REQUEST_SCHEMA_NAME = "external_execution_request"
REQUEST_SCHEMA_VERSION = "1.0.0"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
ARTIFACT_ID_PATTERN = r"^art_[0-9a-f]{20}$"


class ExternalExecutableAuthorizationError(ValueError):
    """Stable error for a raw provider value outside the exact allowlist."""

    code = "DC_EXTERNAL_EXECUTABLE_UNAUTHORIZED"
    reason = "external_executable_id_not_exactly_authorized"
    stage = "external_execution_authorization"

    def __init__(self, raw_value: object) -> None:
        self.raw_type = type(raw_value).__name__
        super().__init__(
            f"{self.code}: external_executable_id is not an exact authorized channel"
        )


def authorize_external_executable_id(raw_value: object) -> ExternalExecutableId:
    """Authorize a raw channel identity without coercion or normalization."""

    if type(raw_value) is not str or raw_value not in APPROVED_EXTERNAL_EXECUTABLE_IDS:
        raise ExternalExecutableAuthorizationError(raw_value)
    return raw_value  # type: ignore[return-value]


class ExternalReferenceInput(BaseModel):
    """One immutable content-addressed input reference."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    artifact_id: str = Field(pattern=ARTIFACT_ID_PATTERN)
    sha256: str = Field(pattern=SHA256_PATTERN)


class ExternalExecutionRequest(BaseModel):
    """Request artifact with no credentials, endpoint, or transport routing."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_name: Literal["external_execution_request"] = REQUEST_SCHEMA_NAME
    schema_version: Literal["1.0.0"] = REQUEST_SCHEMA_VERSION
    request_id: str = Field(pattern=r"^extreq_[0-9a-f]{20}$")
    run_id: str = Field(pattern=r"^run_[0-9a-f]{20}$")
    slide_id: str = Field(min_length=1)
    execution_id: str = Field(pattern=r"^exec_[0-9a-f]{20}$")
    attempt_number: int = Field(ge=1)
    external_executable_id: ExternalExecutableId
    prompt_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    composition_plan_id: str = Field(min_length=1)
    composition_plan_sha256: str = Field(pattern=SHA256_PATTERN)
    requested_model: str = Field(min_length=1)
    requested_width: int = Field(ge=1)
    requested_height: int = Field(ge=1)
    requested_media_type: Literal["image/png", "image/jpeg"]
    references: tuple[ExternalReferenceInput, ...] = Field(default_factory=tuple)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    upstream_artifact_ids: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("external_executable_id", mode="before")
    @classmethod
    def authorize_exact_channel(cls, value: object) -> ExternalExecutableId:
        return authorize_external_executable_id(value)

    @model_validator(mode="after")
    def require_contract_invariants(self) -> "ExternalExecutionRequest":
        if self.requested_width * 9 != self.requested_height * 16:
            raise ValueError("requested dimensions must be exactly 16:9")
        expected_request_id = compute_request_semantic_id(self)
        if self.request_id != expected_request_id:
            raise ValueError("request_id must equal the deterministic semantic request ID")
        if tuple(dict.fromkeys(self.upstream_artifact_ids)) != self.upstream_artifact_ids:
            raise ValueError("upstream_artifact_ids must be unique and ordered")
        return self


def request_semantic_payload(
    request: ExternalExecutionRequest | Mapping[str, object],
) -> dict[str, object]:
    """Return fields defining request meaning, excluding attempt-local identity."""

    payload = (
        request.model_dump(mode="json")
        if isinstance(request, ExternalExecutionRequest)
        else dict(request)
    )
    payload.setdefault("schema_name", REQUEST_SCHEMA_NAME)
    payload.setdefault("schema_version", REQUEST_SCHEMA_VERSION)
    payload.pop("request_id", None)
    payload.pop("execution_id", None)
    payload.pop("attempt_number", None)
    return payload


def compute_request_semantic_id(
    request: ExternalExecutionRequest | Mapping[str, object],
) -> str:
    return stable_id("extreq", request_semantic_payload(request))


def compute_request_semantic_sha256(
    request: ExternalExecutionRequest | Mapping[str, object],
) -> str:
    return content_sha256(request_semantic_payload(request))


def canonical_request_bytes(request: ExternalExecutionRequest) -> bytes:
    """Authoritative bytes: canonical UTF-8 JSON, no Unicode normalization."""

    return canonical_json_bytes(request.model_dump(mode="json"))


def build_external_execution_request(raw_request: object) -> ExternalExecutionRequest:
    """Authorize the raw provider before validating or constructing the request."""

    if type(raw_request) is not dict:
        raise TypeError("external execution request must be a plain object")
    payload = dict(raw_request)
    authorize_external_executable_id(payload.get("external_executable_id"))
    payload.setdefault("schema_name", REQUEST_SCHEMA_NAME)
    payload.setdefault("schema_version", REQUEST_SCHEMA_VERSION)
    payload.setdefault("request_id", compute_request_semantic_id(payload))
    if type(payload.get("references")) is list:
        payload["references"] = tuple(payload["references"])
    if type(payload.get("upstream_artifact_ids")) is list:
        payload["upstream_artifact_ids"] = tuple(payload["upstream_artifact_ids"])
    return ExternalExecutionRequest.model_validate(payload)


@runtime_checkable
class ExternalTransport(Protocol):
    """Injected seam used only to prove that contract-only adapters do not call it."""

    def execute(self, request: ExternalExecutionRequest) -> object:
        ...


@runtime_checkable
class ExternalExecutableAdapter(Protocol):
    enabled: bool
    external_executable_id: ExternalExecutableId
    adapter_id: str

    def execute(
        self,
        request: ExternalExecutionRequest | object,
        transport: ExternalTransport,
    ) -> "ExternalExecutionRecord":
        ...


__all__ = [
    "APPROVED_EXTERNAL_EXECUTABLE_IDS",
    "ARTIFACT_ID_PATTERN",
    "ExternalExecutableAdapter",
    "ExternalExecutableAuthorizationError",
    "ExternalExecutableId",
    "ExternalExecutionRequest",
    "ExternalReferenceInput",
    "ExternalTransport",
    "REQUEST_SCHEMA_NAME",
    "REQUEST_SCHEMA_VERSION",
    "SHA256_PATTERN",
    "authorize_external_executable_id",
    "build_external_execution_request",
    "canonical_request_bytes",
    "compute_request_semantic_id",
    "compute_request_semantic_sha256",
    "request_semantic_payload",
]
