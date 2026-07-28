"""Separate, hash-bound, BLOCKED-only acceptance policy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..identity import canonical_json_bytes, stable_id
from .contracts import ExternalExecutableId
from .record import ExternalExecutionRecord, HashBinding, build_hash_binding
from .verification import (
    ExternalExecutionVerificationReport,
    compute_verification_report_hash,
)


ACCEPTANCE_POLICY_ID = "phase4-external-execution-acceptance-v1-disabled"
ACCEPTANCE_HASH_DOMAIN = "deckcompiler.external_execution.acceptance.v1"


class AcceptancePreconditionError(ValueError):
    code = "DC_EXTERNAL_ACCEPTANCE_PRECONDITION_FAILED"


class ExternalExecutionAcceptance(BaseModel):
    """Policy result that cannot be promoted by provider-controlled content."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_name: Literal["external_execution_acceptance"] = (
        "external_execution_acceptance"
    )
    schema_version: Literal["1.0.0"] = "1.0.0"
    acceptance_id: str = Field(pattern=r"^exaccept_[0-9a-f]{20}$")
    execution_id: str = Field(pattern=r"^exec_[0-9a-f]{20}$")
    record_id: str = Field(pattern=r"^exrec_[0-9a-f]{20}$")
    verifier_report_id: str = Field(pattern=r"^exverify_[0-9a-f]{20}$")
    policy_id: Literal[
        "phase4-external-execution-acceptance-v1-disabled"
    ] = ACCEPTANCE_POLICY_ID
    external_executable_id: ExternalExecutableId
    status: Literal["BLOCKED"] = "BLOCKED"
    accepted: Literal[False] = False
    release_eligible: Literal[False] = False
    reason_codes: tuple[str, ...]
    missing_prerequisites: tuple[str, ...]
    created_at: str = Field(min_length=1)
    evaluator_name: Literal["deckcompiler-external-acceptance-evaluator"] = (
        "deckcompiler-external-acceptance-evaluator"
    )
    evaluator_version: Literal["1.0.0"] = "1.0.0"
    acceptance_hash: HashBinding

    @model_validator(mode="after")
    def require_acceptance_hash_domain(self) -> "ExternalExecutionAcceptance":
        if self.acceptance_hash.hash_domain != ACCEPTANCE_HASH_DOMAIN:
            raise ValueError("acceptance_hash must use the acceptance hash domain")
        return self


def compute_acceptance_record_hash(
    acceptance: ExternalExecutionAcceptance | Mapping[str, Any],
) -> HashBinding:
    payload = (
        acceptance.model_dump(mode="json")
        if isinstance(acceptance, ExternalExecutionAcceptance)
        else dict(acceptance)
    )
    payload.pop("acceptance_hash", None)
    return build_hash_binding(canonical_json_bytes(payload), ACCEPTANCE_HASH_DOMAIN)


def verify_acceptance_record(
    acceptance: ExternalExecutionAcceptance,
    *,
    expected_hash: HashBinding,
) -> bool:
    return (
        expected_hash.hash_domain == ACCEPTANCE_HASH_DOMAIN
        and acceptance.acceptance_hash == expected_hash
        and compute_acceptance_record_hash(acceptance) == expected_hash
        and acceptance.status == "BLOCKED"
        and acceptance.accepted is False
        and acceptance.release_eligible is False
    )


def evaluate_external_execution_acceptance(
    record: ExternalExecutionRecord,
    report: ExternalExecutionVerificationReport | None,
    *,
    created_at: str,
) -> ExternalExecutionAcceptance:
    """Evaluate verified local evidence; current policy always returns BLOCKED."""

    if report is None:
        raise AcceptancePreconditionError("verification report is required")
    if (
        report.final_status != "PASS"
        or report.record_id != record.record_id
        or report.execution_id != record.execution_id
        or compute_verification_report_hash(report) != report.report_hash
    ):
        raise AcceptancePreconditionError(
            "an independently valid verification report is required"
        )

    reasons = (
        "EXTERNAL_TRANSPORT_DISABLED_CONTRACT_ONLY",
        "NO_ACTUAL_PROVIDER_RESPONSE",
        "NO_ACTUAL_OUTPUT",
        "NO_LIVE_IMAGE_GENERATION_EVIDENCE",
        "PHASE4_VISUAL_ARTIFACTS_ABSENT",
        "ACCEPTANCE_NOT_ENABLED",
    )
    missing = (
        "explicit_transport_authorization",
        "canonical_provider_channel_selection",
        "credential_reference_policy",
        "actual_provider_canary",
        "visual_artifact_verification",
        "future_acceptance_state_decision",
    )
    acceptance_id = stable_id(
        "exaccept",
        ACCEPTANCE_POLICY_ID,
        record.record_id,
        report.report_id,
        reasons,
    )
    payload: dict[str, Any] = {
        "schema_name": "external_execution_acceptance",
        "schema_version": "1.0.0",
        "acceptance_id": acceptance_id,
        "execution_id": record.execution_id,
        "record_id": record.record_id,
        "verifier_report_id": report.report_id,
        "policy_id": ACCEPTANCE_POLICY_ID,
        "external_executable_id": record.external_executable_id,
        "status": "BLOCKED",
        "accepted": False,
        "release_eligible": False,
        "reason_codes": reasons,
        "missing_prerequisites": missing,
        "created_at": created_at,
        "evaluator_name": "deckcompiler-external-acceptance-evaluator",
        "evaluator_version": "1.0.0",
    }
    payload["acceptance_hash"] = compute_acceptance_record_hash(payload).model_dump(
        mode="json"
    )
    return ExternalExecutionAcceptance.model_validate(payload)


__all__ = [
    "ACCEPTANCE_HASH_DOMAIN",
    "ACCEPTANCE_POLICY_ID",
    "AcceptancePreconditionError",
    "ExternalExecutionAcceptance",
    "compute_acceptance_record_hash",
    "evaluate_external_execution_acceptance",
    "verify_acceptance_record",
]
