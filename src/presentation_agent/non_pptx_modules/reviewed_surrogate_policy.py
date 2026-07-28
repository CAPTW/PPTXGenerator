"""Reviewed-surrogate policy registry and deterministic PR/release consumption helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class GateDecisionCategory(StrEnum):
    PASS = "pass"
    PASS_WITH_WARNING = "pass_with_warning"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class TargetStatus(StrEnum):
    APPROVED = "approved"
    REVIEWED = "reviewed"
    DRAFT = "draft"
    RETIRED = "retired"


class PolicyContext(StrEnum):
    PR = "pr"
    RELEASE = "release"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)


class PolicyProfileSpec(Contract):
    profile_id: str
    description: str | None = None
    status: TargetStatus = TargetStatus.REVIEWED


class PolicyPackSpec(Contract):
    pack_id: str
    profile_ids: list[str] = Field(default_factory=list)
    status: TargetStatus = TargetStatus.REVIEWED
    purpose: str = "reviewed-surrogate pack"


class ReviewedSurrogatePolicyFile(Contract):
    """Registry-style policy file for reviewed-surrogate scenarios."""

    policy_id: str
    policy_version: str = "1.0"
    profiles: list[PolicyProfileSpec] = Field(default_factory=list)
    packs: list[PolicyPackSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_references(self) -> "ReviewedSurrogatePolicyFile":
        profile_ids = {profile.profile_id for profile in self.profiles}
        pack_ids: set[str] = set()
        for pack in self.packs:
            if pack.pack_id in pack_ids:
                raise ValueError(f"duplicate pack_id {pack.pack_id!r}")
            pack_ids.add(pack.pack_id)
            unknown_profiles = set(pack.profile_ids) - profile_ids
            if unknown_profiles:
                sorted_unknown = ", ".join(sorted(unknown_profiles))
                raise ValueError(f"pack {pack.pack_id!r} references unknown profile ids: {sorted_unknown}")
        return self


class ArtifactExpectation(Contract):
    artifact_path: str
    required: bool = True
    rationale: str | None = None


class ValidationTargetRecord(Contract):
    """One reviewed target entry."""

    validation_target_id: str
    pack_id: str
    policy_file: str
    policy_profile: str | None = None
    status: TargetStatus
    owner: str
    reviewer: str | None = None
    purpose: str
    active_surrogate_ids: list[str] = Field(default_factory=list)
    expected_inactive_untouched_ids: list[str] = Field(default_factory=list)
    report_artifact_expectations: list[ArtifactExpectation] = Field(default_factory=list)
    applies_to_pr: bool = True
    applies_to_release: bool = False
    blocking_for_pr: bool = True
    blocking_for_release: bool = True
    notes: str | None = None
    limitations: str | None = None

    @model_validator(mode="after")
    def _validate_applicability(self) -> "ValidationTargetRecord":
        if not self.applies_to_pr and not self.applies_to_release:
            raise ValueError("validation target must apply to at least one of PR or release")
        return self


class ValidationTargetRegistry(Contract):
    registry_id: str
    purpose: str = "approved reviewed-surrogate validation targets"
    owner: str = "unspecified"
    validation_targets: list[ValidationTargetRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_targets(self) -> "ValidationTargetRegistry":
        seen: set[str] = set()
        for target in self.validation_targets:
            if target.validation_target_id in seen:
                raise ValueError(f"duplicate validation_target_id {target.validation_target_id!r}")
            seen.add(target.validation_target_id)
        return self


class ProvenanceRecord(Contract):
    surrogate_id: str
    tier: str
    lifecycle_state: str
    provenance_complete: bool = True
    supersession_ref: str | None = None


class ReviewedSurrogateValidationGate(Contract):
    """Input artifact produced by the reviewed-surrogate gate."""

    gate_report_id: str
    validation_target_id: str
    validation_target_pack_id: str
    overall_passed: bool
    default_manual_passed: bool
    reviewed_pack_passed: bool
    required_artifact_presence: bool
    provenance_completeness: bool
    supersession_compliance: bool
    untouched_lower_priority_active_count: int = 0
    active_surrogate_ids: list[str] = Field(default_factory=list)
    inactive_untouched_ids: list[str] = Field(default_factory=list)
    required_artifact_paths: list[str] = Field(default_factory=list)
    provenance_records: list[ProvenanceRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_counting(self) -> "ReviewedSurrogateValidationGate":
        if self.untouched_lower_priority_active_count < 0:
            raise ValueError("untouched_lower_priority_active_count cannot be negative")
        if self.untouched_lower_priority_active_count != len(self.inactive_untouched_ids):
            raise ValueError(
                "untouched_lower_priority_active_count must match inactive_untouched_ids length"
            )
        return self


class PolicyEvaluationCheck(Contract):
    name: str
    passed: bool
    details: str


class PolicyEvaluationReport(Contract):
    report_id: str
    validation_target_id: str
    validation_target_pack_id: str
    target_registry_status: str
    policy_file_id: str
    policy_context: str
    policy_decision: GateDecisionCategory
    gate_input_artifact_path: str
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_follow_up: list[str] = Field(default_factory=list)
    pr_merge_allowed: bool
    release_promotion_allowed: bool
    blocking: bool
    checks: list[PolicyEvaluationCheck] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def _load_yaml_or_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        if path.suffix.lower() in {".yaml", ".yml"}:
            payload = yaml.safe_load(f)
        else:
            payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"top-level payload in {path} must be a JSON/YAML object")
    return payload


def load_validation_policy_file(path: str | Path) -> ReviewedSurrogatePolicyFile:
    payload = _load_yaml_or_json(Path(path))
    return ReviewedSurrogatePolicyFile.model_validate(payload)


def load_validation_target_registry(path: str | Path) -> ValidationTargetRegistry:
    payload = _load_yaml_or_json(Path(path))
    return ValidationTargetRegistry.model_validate(payload)


def load_reviewed_surrogate_gate(path: str | Path) -> ReviewedSurrogateValidationGate:
    payload = _load_yaml_or_json(Path(path))
    return ReviewedSurrogateValidationGate.model_validate(payload)


def _resolve_contexts(context: PolicyContext | str) -> list[PolicyContext]:
    normalized = context.value if isinstance(context, PolicyContext) else str(context).strip().lower()
    if normalized == "both":
        return [PolicyContext.PR, PolicyContext.RELEASE]
    if normalized == "pr":
        return [PolicyContext.PR]
    if normalized == "release":
        return [PolicyContext.RELEASE]
    raise ValueError(f"unsupported policy context {context!r}")


def _resolve_policy_path(
    record: ValidationTargetRecord,
    registry_path: Path,
    context_root: Path,
) -> Path:
    candidate = Path(record.policy_file)
    if candidate.is_absolute():
        return candidate
    if (context_root / candidate).exists():
        return context_root / candidate
    if (registry_path.parent / candidate).exists():
        return registry_path.parent / candidate
    return context_root / candidate


def _find_target(registry: ValidationTargetRegistry, target_id: str) -> ValidationTargetRecord:
    for target in registry.validation_targets:
        if target.validation_target_id == target_id:
            return target
    raise KeyError(f"unknown validation_target_id {target_id!r}")


def _find_pack(policy_file: ReviewedSurrogatePolicyFile, pack_id: str) -> PolicyPackSpec | None:
    for pack in policy_file.packs:
        if pack.pack_id == pack_id:
            return pack
    return None


def _pack_profile_status_check(
    policy_file: ReviewedSurrogatePolicyFile,
    pack: PolicyPackSpec,
    profile_id: str | None,
) -> None:
    if profile_id is None:
        return
    if profile_id not in pack.profile_ids:
        raise ValueError(f"target references policy_profile {profile_id!r} not assigned to pack {pack.pack_id!r}")
    profile_map = {profile.profile_id: profile for profile in policy_file.profiles}
    profile = profile_map.get(profile_id)
    if profile is None:
        raise ValueError(f"target references unknown policy_profile {profile_id!r}")
    if profile.status not in {TargetStatus.APPROVED, TargetStatus.REVIEWED}:
        raise ValueError(f"policy_profile {profile_id!r} is not approved/reviewed")


def _resolve_context_flags(target: ValidationTargetRecord, context: PolicyContext) -> tuple[bool, bool]:
    if context == PolicyContext.PR:
        return target.applies_to_pr, target.blocking_for_pr
    return target.applies_to_release, target.blocking_for_release


def _artifact_exists(context_root: Path, candidate: str) -> bool:
    artifact_path = Path(candidate)
    if not artifact_path.is_absolute():
        artifact_path = context_root / artifact_path
    return artifact_path.exists()


def _append_check(checks: list[PolicyEvaluationCheck], *, name: str, passed: bool, details: str) -> None:
    checks.append(PolicyEvaluationCheck(name=name, passed=passed, details=details))


def evaluate_reviewed_surrogate_policy(
    *,
    gate_artifact_path: str | Path,
    registry_path: str | Path,
    target_id: str,
    context: PolicyContext | str = "both",
    context_root: str | Path | None = None,
) -> dict[str, PolicyEvaluationReport]:
    """Evaluate a reviewed-surrogate gate artifact for PR and/or release contexts."""

    root = Path(context_root or Path.cwd()).resolve()
    registry_path_obj = Path(registry_path)
    gate_path = Path(gate_artifact_path)

    registry = load_validation_target_registry(registry_path_obj)
    target = _find_target(registry, target_id)
    gate = load_reviewed_surrogate_gate(gate_path)
    policy_path = _resolve_policy_path(target, registry_path_obj, root)

    if target.status not in {TargetStatus.APPROVED, TargetStatus.REVIEWED}:
        raise ValueError(f"target {target.validation_target_id!r} is not approved/reviewed")
    if gate.validation_target_id != target.validation_target_id:
        raise ValueError("validation target mismatch between gate artifact and registry entry")
    if gate.validation_target_pack_id != target.pack_id:
        raise ValueError("validation target pack mismatch between gate artifact and registry entry")
    if not target.report_artifact_expectations:
        raise ValueError(f"target {target.validation_target_id!r} has no report artifact expectations configured")
    if not policy_path.exists():
        raise FileNotFoundError(f"policy file not found: {policy_path}")

    policy_file = load_validation_policy_file(policy_path)
    pack = _find_pack(policy_file, target.pack_id)
    if pack is None:
        raise ValueError(f"target references unknown pack_id {target.pack_id!r}")
    if pack.status not in {TargetStatus.APPROVED, TargetStatus.REVIEWED}:
        raise ValueError(f"pack {target.pack_id!r} is not approved/reviewed")
    _pack_profile_status_check(policy_file, pack, target.policy_profile)

    outputs: dict[str, PolicyEvaluationReport] = {}
    contexts = _resolve_contexts(context)

    target_scope = set(target.active_surrogate_ids)
    gate_scope = set(gate.active_surrogate_ids)
    gate_provenance = {row.surrogate_id: row for row in gate.provenance_records}
    required_artifacts = {expect.artifact_path: expect.required for expect in target.report_artifact_expectations}
    expected_inactive = set(target.expected_inactive_untouched_ids)
    reported_inactive = set(gate.inactive_untouched_ids)
    gate_artifacts = set(gate.required_artifact_paths)

    for policy_context in contexts:
        checks: list[PolicyEvaluationCheck] = []
        reasons: list[str] = []
        warnings: list[str] = []
        follow_up: list[str] = []

        applicable, blocking = _resolve_context_flags(target, policy_context)
        if not applicable:
            _append_check(
                checks,
                name="context_applicability",
                passed=False,
                details=f"Target is not applicable for {policy_context.value} context.",
            )
            outputs[policy_context.value] = PolicyEvaluationReport(
                report_id=f"{target.validation_target_id}-{policy_context.value}-policy-report",
                validation_target_id=target.validation_target_id,
                validation_target_pack_id=target.pack_id,
                target_registry_status=target.status.value,
                policy_file_id=f"{policy_path}:{target.policy_profile or 'default'}",
                policy_context=policy_context.value,
                policy_decision=GateDecisionCategory.NOT_APPLICABLE,
                gate_input_artifact_path=str(gate_path),
                reasons=[],
                warnings=[f"Target is not applicable for {policy_context.value} context."],
                required_follow_up=[],
                pr_merge_allowed=True if policy_context == PolicyContext.PR else False,
                release_promotion_allowed=True if policy_context == PolicyContext.RELEASE else False,
                blocking=False,
                checks=checks,
            )
            continue

        has_failures = False

        _append_check(
            checks,
            name="default_manual_passed",
            passed=bool(gate.default_manual_passed),
            details="default/manual baseline passed." if gate.default_manual_passed else "default/manual baseline failed.",
        )
        if not gate.default_manual_passed:
            has_failures = True
            reasons.append("default/manual baseline must pass; reviewed mode cannot override baseline.")

        _append_check(
            checks,
            name="reviewed_pack_passed",
            passed=bool(gate.reviewed_pack_passed),
            details="reviewed pack validation passed." if gate.reviewed_pack_passed else "reviewed pack validation failed.",
        )
        if not gate.reviewed_pack_passed:
            has_failures = True
            reasons.append("reviewed surrogate pack validation failed.")

        _append_check(
            checks,
            name="overall_passed",
            passed=bool(gate.overall_passed),
            details="gate reported overall pass." if gate.overall_passed else "gate reported overall failure.",
        )
        if not gate.overall_passed:
            has_failures = True
            reasons.append("the reviewed-surrogate gate reported overall failure.")

        _append_check(
            checks,
            name="required_artifact_presence",
            passed=bool(gate.required_artifact_presence),
            details=(
                "required artifact presence was reported as true."
                if gate.required_artifact_presence
                else "required artifact presence was reported as false."
            ),
        )
        if not gate.required_artifact_presence:
            has_failures = True
            reasons.append("required artifact presence check failed.")

        _append_check(
            checks,
            name="provenance_completeness",
            passed=bool(gate.provenance_completeness),
            details=(
                "provenance completeness reported true."
                if gate.provenance_completeness
                else "provenance completeness reported false."
            ),
        )
        if not gate.provenance_completeness:
            has_failures = True
            reasons.append("provenance completeness check failed.")

        _append_check(
            checks,
            name="supersession_compliance",
            passed=bool(gate.supersession_compliance),
            details=(
                "supersession compliance reported true." if gate.supersession_compliance else "supersession compliance failed."
            ),
        )
        if not gate.supersession_compliance:
            has_failures = True
            reasons.append("supersession compliance check failed.")

        untouched_ok = gate.untouched_lower_priority_active_count == 0
        _append_check(
            checks,
            name="untouched_lower_priority_active_count",
            passed=untouched_ok,
            details=f"untouched lower-priority active count = {gate.untouched_lower_priority_active_count}.",
        )
        if not untouched_ok:
            has_failures = True
            reasons.append("untouched lower-priority gap activation would occur.")

        expected_inactive_match = expected_inactive == reported_inactive
        _append_check(
            checks,
            name="expected_inactive_match",
            passed=expected_inactive_match,
            details=f"expected_inactive={sorted(expected_inactive)}, reported_inactive={sorted(reported_inactive)}.",
        )
        if not expected_inactive_match:
            has_failures = True
            reasons.append("reported inactive untouched IDs do not match registry expectation.")

        scope_contains_registered = target_scope.issubset(gate_scope)
        _append_check(
            checks,
            name="scope_contains_all_active_surrogates",
            passed=scope_contains_registered,
            details=(
                "all registry-approved active surrogates are included in gate scope."
                if scope_contains_registered
                else "gate scope is missing registry-approved active surrogates."
            ),
        )
        if not scope_contains_registered:
            has_failures = True
            reasons.append(f"missing active ids: {sorted(target_scope - gate_scope)}")

        scope_no_unapproved = gate_scope.issubset(target_scope)
        _append_check(
            checks,
            name="scope_no_unapproved_active_ids",
            passed=scope_no_unapproved,
            details=(
                "gate scope contains no unapproved active IDs."
                if scope_no_unapproved
                else "gate scope includes unapproved active IDs."
            ),
        )
        if not scope_no_unapproved:
            has_failures = True
            reasons.append(f"unapproved active IDs were activated: {sorted(gate_scope - target_scope)}")

        for artifact_path, required in required_artifacts.items():
            in_gate = artifact_path in gate_artifacts
            _append_check(
                checks,
                name=f"required_artifact::{artifact_path}",
                passed=(not required) or in_gate,
                details=(
                    f"required artifact {artifact_path!r} was present in gate artifact."
                    if (not required) or in_gate
                    else f"required artifact {artifact_path!r} is missing from gate artifact."
                ),
            )
            if required and not in_gate:
                has_failures = True
                reasons.append(f"required artifact {artifact_path!r} missing from gate artifact.")
                continue
            if in_gate and required and not _artifact_exists(root, artifact_path):
                _append_check(
                    checks,
                    name=f"required_artifact_exists::{artifact_path}",
                    passed=False,
                    details=f"required artifact {artifact_path!r} was not found under context root.",
                )
                has_failures = True
                reasons.append(f"required artifact {artifact_path!r} missing in filesystem.")
            elif in_gate and required:
                _append_check(
                    checks,
                    name=f"required_artifact_exists::{artifact_path}",
                    passed=True,
                    details=f"required artifact {artifact_path!r} exists under context root.",
                )

        for surrogate_id in sorted(target_scope):
            record = gate_provenance.get(surrogate_id)
            provenance_ok = (
                record is not None
                and bool(record.provenance_complete)
                and bool((record.tier or "").strip())
                and bool((record.lifecycle_state or "").strip())
            )
            _append_check(
                checks,
                name=f"provenance_record::{surrogate_id}",
                passed=provenance_ok,
                details="provenance record is complete." if provenance_ok else f"provenance missing or incomplete for {surrogate_id!r}.",
            )
            if not provenance_ok:
                has_failures = True
                reasons.append(f"provenance incomplete for active surrogate {surrogate_id!r}")

        for surrogate_id in sorted(gate_scope - target_scope):
            _append_check(
                checks,
                name=f"scope_guard::{surrogate_id}",
                passed=False,
                details=f"gate activated surrogate id outside registered scope: {surrogate_id!r}.",
            )
            has_failures = True
            reasons.append(f"gate activated unapproved surrogate {surrogate_id!r}")

        if has_failures and blocking:
            decision = GateDecisionCategory.FAIL
            follow_up.append("Resolve blocking failures before PR merge/release promotion.")
            warnings.append("Blocking reviewed target failures found.")
            pr_merge_allowed = policy_context == PolicyContext.PR and False
            release_promotion_allowed = policy_context == PolicyContext.RELEASE and False
        elif has_failures and not blocking:
            decision = GateDecisionCategory.PASS_WITH_WARNING
            follow_up.append("Advisory reviewed-target failures present; baseline manual mode remains primary.")
            warnings.append("Advisory failures do not block merge or promotion.")
            pr_merge_allowed = policy_context == PolicyContext.PR
            release_promotion_allowed = policy_context == PolicyContext.RELEASE
        else:
            if blocking:
                decision = GateDecisionCategory.PASS
                follow_up = []
                warnings.append("Reviewed target passed as a blocking secondary validation.")
            else:
                decision = GateDecisionCategory.PASS_WITH_WARNING
                follow_up.append("Target is advisory and passed; it is non-certifying.")
                warnings.append("Manual/runtime truth remains the primary baseline.")
            pr_merge_allowed = policy_context == PolicyContext.PR
            release_promotion_allowed = policy_context == PolicyContext.RELEASE

        outputs[policy_context.value] = PolicyEvaluationReport(
            report_id=f"{target.validation_target_id}-{policy_context.value}-policy-report",
            validation_target_id=target.validation_target_id,
            validation_target_pack_id=target.pack_id,
            target_registry_status=target.status.value,
            policy_file_id=f"{policy_path}:{target.policy_profile or 'default'}",
            policy_context=policy_context.value,
            policy_decision=decision,
            gate_input_artifact_path=str(gate_path),
            reasons=list(dict.fromkeys(reasons)),
            warnings=list(dict.fromkeys(warnings)),
            required_follow_up=list(dict.fromkeys(follow_up)),
            pr_merge_allowed=pr_merge_allowed,
            release_promotion_allowed=release_promotion_allowed,
            blocking=blocking,
            checks=checks,
        )

    return outputs


def write_reviewed_surrogate_policy_reports(
    reports: dict[str, PolicyEvaluationReport],
    output_dir: str | Path,
) -> dict[str, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for context, report in reports.items():
        if context == PolicyContext.PR.value:
            path = root / "reviewed-surrogate-pr-policy-report.json"
        elif context == PolicyContext.RELEASE.value:
            path = root / "reviewed-surrogate-release-gate.json"
        else:
            path = root / f"reviewed-surrogate-{context}-policy-report.json"
        path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        written[context] = path
    return written
