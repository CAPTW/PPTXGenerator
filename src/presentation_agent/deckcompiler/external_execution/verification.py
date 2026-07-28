"""Independent byte verification for fail-closed external-execution records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..identity import canonical_json_bytes, stable_id
from .contracts import ExternalExecutionRequest, canonical_request_bytes
from .record import (
    BLOCKED_REASON,
    HashBinding,
    HashDomain,
    REQUEST_HASH_DOMAIN,
    ExternalExecutionRecord,
    build_hash_binding,
    compute_execution_record_hash,
    resolve_approved_path,
)


VERIFICATION_REPORT_HASH_DOMAIN = (
    "deckcompiler.external_execution.verification_report.v1"
)


class ExternalExecutionVerificationReport(BaseModel):
    """Immutable verification facts; a PASS is not execution acceptance."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_name: Literal["external_execution_verification_report"] = (
        "external_execution_verification_report"
    )
    schema_version: Literal["1.0.0"] = "1.0.0"
    verifier_name: Literal["deckcompiler-external-execution-verifier"] = (
        "deckcompiler-external-execution-verifier"
    )
    verifier_version: Literal["1.0.0"] = "1.0.0"
    report_id: str = Field(pattern=r"^exverify_[0-9a-f]{20}$")
    execution_id: str = Field(pattern=r"^exec_[0-9a-f]{20}$")
    record_id: str = Field(pattern=r"^exrec_[0-9a-f]{20}$")
    verified_artifact_ids: tuple[str, ...]
    request_verification_status: Literal["valid", "invalid"]
    response_verification_status: Literal["absent_expected", "invalid"]
    output_verification_statuses: tuple[Literal["valid", "invalid"], ...]
    record_verification_status: Literal["valid", "invalid"]
    provenance_verification_status: Literal["valid", "invalid"]
    transport_policy_verification_status: Literal["valid", "invalid"]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    final_status: Literal["PASS", "FAIL"]
    created_at: str = Field(min_length=1)
    report_hash: HashBinding

    @model_validator(mode="after")
    def require_report_hash_domain(self) -> "ExternalExecutionVerificationReport":
        if self.report_hash.hash_domain != VERIFICATION_REPORT_HASH_DOMAIN:
            raise ValueError("report_hash must use the verification-report domain")
        return self


def verify_hash_binding(
    actual_bytes: bytes,
    binding: HashBinding,
    *,
    expected_domain: HashDomain,
) -> tuple[str, ...]:
    """Recompute one binding without trusting any declared digest or length."""

    issues: list[str] = []
    if binding.algorithm != "sha256":
        issues.append("HASH_ALGORITHM_UNSUPPORTED")
    if binding.hash_domain != expected_domain:
        issues.append("HASH_DOMAIN_MISMATCH")
    recomputed = build_hash_binding(actual_bytes, expected_domain)
    if binding.byte_count != recomputed.byte_count:
        issues.append("HASH_BYTE_COUNT_MISMATCH")
    if binding.digest != recomputed.digest:
        issues.append("HASH_DIGEST_MISMATCH")
    return tuple(issues)


def compute_verification_report_hash(
    report: ExternalExecutionVerificationReport | Mapping[str, Any],
) -> HashBinding:
    payload = (
        report.model_dump(mode="json")
        if isinstance(report, ExternalExecutionVerificationReport)
        else dict(report)
    )
    payload.pop("report_hash", None)
    return build_hash_binding(
        canonical_json_bytes(payload),
        VERIFICATION_REPORT_HASH_DOMAIN,
    )


def verify_external_execution_record(
    *,
    run_root: str | Path,
    record_relative_path: str,
    expected_record: ExternalExecutionRecord,
    expected_request: ExternalExecutionRequest,
    known_input_artifact_ids: tuple[str, ...],
    created_at: str,
) -> ExternalExecutionVerificationReport:
    """Read record/request bytes and validate them against independent expectations."""

    errors: list[str] = []
    warnings: list[str] = []

    def add(code: str) -> None:
        if code not in errors:
            errors.append(code)

    stored_record: ExternalExecutionRecord | None = None
    raw_payload: object | None = None
    try:
        record_path = resolve_approved_path(
            run_root, record_relative_path, must_exist=True
        )
        record_bytes = record_path.read_bytes()
        try:
            raw_payload = json.loads(record_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            add("RECORD_ARTIFACT_INVALID")
        if isinstance(raw_payload, dict):
            if raw_payload != expected_record.model_dump(mode="json"):
                add("EXPECTED_RECORD_MISMATCH")
            try:
                stored_record = ExternalExecutionRecord.model_validate_json(
                    record_bytes
                )
            except Exception:
                add("RECORD_ARTIFACT_INVALID")
            if stored_record is not None:
                canonical_stored = canonical_json_bytes(
                    stored_record.model_dump(mode="json")
                )
                if record_bytes != canonical_stored:
                    add("NON_CANONICAL_RECORD_BYTES")
                actual_record_hash = compute_execution_record_hash(stored_record)
                if actual_record_hash != stored_record.record_hash:
                    add("EXECUTION_RECORD_HASH_MISMATCH")
                if stored_record.record_hash != expected_record.record_hash:
                    add("EXPECTED_RECORD_HASH_MISMATCH")
        elif raw_payload is not None:
            add("RECORD_ARTIFACT_INVALID")
    except Exception:
        add("RECORD_PATH_OR_READ_FAILURE")

    record_for_checks = stored_record or expected_record
    request_error_codes = {
        "REQUEST_PATH_OR_READ_FAILURE",
        "REQUEST_ARTIFACT_INVALID",
        "REQUEST_ARTIFACT_MISMATCH",
        "REQUEST_HASH_ALGORITHM_UNSUPPORTED",
        "REQUEST_HASH_DOMAIN_MISMATCH",
        "REQUEST_HASH_BYTE_COUNT_MISMATCH",
        "REQUEST_HASH_DIGEST_MISMATCH",
        "REQUEST_IDENTITY_MISMATCH",
    }
    try:
        request_path = resolve_approved_path(
            run_root,
            record_for_checks.request_artifact.relative_path,
            must_exist=True,
        )
        request_bytes = request_path.read_bytes()
        expected_request_bytes = canonical_request_bytes(expected_request)
        for issue in verify_hash_binding(
            request_bytes,
            record_for_checks.request_artifact.hash,
            expected_domain=REQUEST_HASH_DOMAIN,
        ):
            add(f"REQUEST_{issue}")
        if request_bytes != expected_request_bytes:
            add("REQUEST_ARTIFACT_MISMATCH")
        try:
            parsed_request = ExternalExecutionRequest.model_validate_json(request_bytes)
        except Exception:
            add("REQUEST_ARTIFACT_INVALID")
        else:
            if parsed_request != expected_request:
                add("REQUEST_ARTIFACT_MISMATCH")
            if (
                parsed_request.execution_id != record_for_checks.execution_id
                or parsed_request.request_id != record_for_checks.request_id
                or parsed_request.run_id != record_for_checks.run_id
                or parsed_request.external_executable_id
                != record_for_checks.external_executable_id
                or parsed_request.source_commit != record_for_checks.source_commit
            ):
                add("REQUEST_IDENTITY_MISMATCH")
    except Exception:
        add("REQUEST_PATH_OR_READ_FAILURE")

    actual_input_ids = tuple(
        item.artifact_id for item in record_for_checks.input_artifacts
    )
    if actual_input_ids != expected_request.upstream_artifact_ids:
        add("INPUT_ARTIFACT_RELATION_MISMATCH")
    if any(item not in known_input_artifact_ids for item in actual_input_ids):
        add("INPUT_ARTIFACT_UNRESOLVED")
    if record_for_checks.source_commit != expected_request.source_commit:
        add("SOURCE_COMMIT_MISMATCH")
    if (
        record_for_checks.implementation_provenance.source_commit
        != record_for_checks.source_commit
    ):
        add("IMPLEMENTATION_PROVENANCE_MISMATCH")
    if (
        record_for_checks.execution_lane != "contract_only"
        or record_for_checks.status != "blocked"
        or record_for_checks.transport_attempted is not False
        or record_for_checks.transport_call_count != 0
        or record_for_checks.blocked_reason != BLOCKED_REASON
    ):
        add("TRANSPORT_POLICY_VIOLATION")
    if (
        record_for_checks.response_artifact is not None
        or record_for_checks.response_hash is not None
        or record_for_checks.outputs
    ):
        add("BLOCKED_ARTIFACT_ABSENCE_VIOLATION")

    request_status = (
        "invalid" if any(code in request_error_codes for code in errors) else "valid"
    )
    record_codes = {
        "RECORD_ARTIFACT_INVALID",
        "RECORD_PATH_OR_READ_FAILURE",
        "NON_CANONICAL_RECORD_BYTES",
        "EXECUTION_RECORD_HASH_MISMATCH",
        "EXPECTED_RECORD_HASH_MISMATCH",
        "EXPECTED_RECORD_MISMATCH",
    }
    record_status = "invalid" if any(code in record_codes for code in errors) else "valid"
    provenance_status = (
        "invalid"
        if any(
            code in {"SOURCE_COMMIT_MISMATCH", "IMPLEMENTATION_PROVENANCE_MISMATCH"}
            for code in errors
        )
        else "valid"
    )
    transport_status = (
        "invalid"
        if any(
            code in {"TRANSPORT_POLICY_VIOLATION", "BLOCKED_ARTIFACT_ABSENCE_VIOLATION"}
            for code in errors
        )
        else "valid"
    )
    response_status = (
        "invalid"
        if "BLOCKED_ARTIFACT_ABSENCE_VIOLATION" in errors
        else "absent_expected"
    )
    final_status = "FAIL" if errors else "PASS"
    verified_ids = (
        expected_record.record_id,
        expected_request.request_id,
        *known_input_artifact_ids,
    )
    report_id = stable_id(
        "exverify",
        expected_record.record_id,
        expected_record.record_hash.digest,
        tuple(errors),
        created_at,
    )
    payload: dict[str, Any] = {
        "schema_name": "external_execution_verification_report",
        "schema_version": "1.0.0",
        "verifier_name": "deckcompiler-external-execution-verifier",
        "verifier_version": "1.0.0",
        "report_id": report_id,
        "execution_id": expected_record.execution_id,
        "record_id": expected_record.record_id,
        "verified_artifact_ids": verified_ids,
        "request_verification_status": request_status,
        "response_verification_status": response_status,
        "output_verification_statuses": (),
        "record_verification_status": record_status,
        "provenance_verification_status": provenance_status,
        "transport_policy_verification_status": transport_status,
        "errors": tuple(errors),
        "warnings": tuple(warnings),
        "final_status": final_status,
        "created_at": created_at,
    }
    payload["report_hash"] = compute_verification_report_hash(payload).model_dump(
        mode="json"
    )
    return ExternalExecutionVerificationReport.model_validate(payload)


__all__ = [
    "ExternalExecutionVerificationReport",
    "VERIFICATION_REPORT_HASH_DOMAIN",
    "compute_verification_report_hash",
    "verify_external_execution_record",
    "verify_hash_binding",
]
