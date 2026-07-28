"""Shared proof-unit registry policies for direct workflow-family consumers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Mapping

from ..compat.legacy_non_pptx import ProofCoverageClass, SlideRole


class SharedProofCompatMode(StrEnum):
    NONE = "none"
    LEGACY_MANIFEST_MIGRATION_ONLY = "legacy-manifest-migration-only"


PROOF_UNIT_REGISTRY_FINGERPRINT_KEY = "proof_unit_registry"
LEGACY_PROOF_MODULE_MANIFEST_FINGERPRINT_KEY = "proof_module_manifest"
PROOF_FINGERPRINT_KEY_ALIASES = frozenset({LEGACY_PROOF_MODULE_MANIFEST_FINGERPRINT_KEY})
PROOF_ARTIFACT_CONTRACT_VERSION = "2.0"
PROOF_ARTIFACT_NORMAL_PERSISTENCE_MODE = "registry-only"
PROOF_ARTIFACT_SUNSET_PHASE = "retirement-prep"
PROOF_ARTIFACT_COMPAT_WARNING_SCOPE = "explicit-compat-cli-only"
PROOF_FINGERPRINT_ALIAS_READ_SCOPE = "pipeline-state-recollection-only"


class LegacyManifestSurfaceClassification(StrEnum):
    REQUIRED_BACKWARD_COMPAT = "required_backward_compat"
    COMPAT_ONLY_BUT_ISOLATED = "compat_only_but_isolated"
    NORMAL_PATH_DEBT = "normal_path_debt"
    EXAMPLE_OR_FIXTURE_DEBT = "example_or_fixture_debt"
    UNKNOWN_UNTIL_FURTHER_AUDIT = "unknown_until_further_audit"


class LegacyManifestSurfaceSunsetStatus(StrEnum):
    STILL_BLOCKING = "still-blocking"
    COMPAT_ONLY_ISOLATED = "compat-only-isolated"
    REQUIRED_FOR_ACTIVE_COMPAT = "required-for-active-compat"
    UNKNOWN_OR_DEFERRED = "unknown-or-deferred"


class ProofArtifactWorkspaceMode(StrEnum):
    NOT_APPLICABLE = "not-applicable"
    REGISTRY_ONLY = "registry-only"
    MANIFEST_ONLY = "manifest-only"
    MIXED = "mixed"
    MISSING = "missing"


class ProofArtifactNormalizationMode(StrEnum):
    NOT_APPLICABLE = "not-applicable"
    REGISTRY_ONLY_CLEAN = "registry-only-clean"
    REGISTRY_ONLY_ALIAS_ACTIVE = "registry-only-alias-active"
    MANIFEST_ONLY = "manifest-only"
    MIXED = "mixed"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class LegacyManifestSurfaceAuditRow:
    surface_id: str
    location: str
    classification: LegacyManifestSurfaceClassification
    sunset_status: LegacyManifestSurfaceSunsetStatus
    rationale: str


@dataclass(frozen=True, slots=True)
class SharedProofConsumerPolicy:
    option_id: str
    expected_non_appendix_sections: tuple[str, ...]
    claim_anchor_section_title: str
    bridge_section_titles: tuple[str, ...]
    proof_section_title: str
    synthesis_anchor_section_title: str
    unit_id_prefix: str
    unit_minimum: int
    allowed_unit_roles: tuple[SlideRole, ...]
    required_unit_roles: tuple[SlideRole, ...]
    minimum_direct_evidence_units: int
    minimum_synthesis_units: int
    compat_mode: SharedProofCompatMode
    claim_link_reason: str
    synthesis_link_reason: str


SHARED_PROOF_CONSUMER_POLICIES: dict[str, SharedProofConsumerPolicy] = {
    "evidence-backed-core": SharedProofConsumerPolicy(
        option_id="evidence-backed-core",
        expected_non_appendix_sections=("Core Claim", "Proof Modules", "Implications"),
        claim_anchor_section_title="Core Claim",
        bridge_section_titles=(),
        proof_section_title="Proof Modules",
        synthesis_anchor_section_title="Implications",
        unit_id_prefix="evidence-backed-core-proof",
        unit_minimum=2,
        allowed_unit_roles=(SlideRole.EVIDENCE, SlideRole.COMPARISON, SlideRole.ANALYSIS),
        required_unit_roles=(),
        minimum_direct_evidence_units=1,
        minimum_synthesis_units=1,
        compat_mode=SharedProofCompatMode.LEGACY_MANIFEST_MIGRATION_ONLY,
        claim_link_reason="The module belongs to the explicit evidence-backed core proof stack and directly supports the core-claim opening.",
        synthesis_link_reason="The module remains in the main story because its proof must flow directly into the implications close.",
    ),
    "report-with-decision-cut": SharedProofConsumerPolicy(
        option_id="report-with-decision-cut",
        expected_non_appendix_sections=(
            "Executive Summary",
            "Why Now",
            "Proof And Options",
            "Recommendation And Next Steps",
        ),
        claim_anchor_section_title="Executive Summary",
        bridge_section_titles=("Why Now",),
        proof_section_title="Proof And Options",
        synthesis_anchor_section_title="Recommendation And Next Steps",
        unit_id_prefix="report-with-decision-cut-proof",
        unit_minimum=3,
        allowed_unit_roles=(SlideRole.EVIDENCE, SlideRole.COMPARISON, SlideRole.ANALYSIS),
        required_unit_roles=(SlideRole.EVIDENCE, SlideRole.COMPARISON, SlideRole.ANALYSIS),
        minimum_direct_evidence_units=1,
        minimum_synthesis_units=2,
        compat_mode=SharedProofCompatMode.NONE,
        claim_link_reason="The unit belongs to the report decision-cut proof stack and directly supports the executive decision framing.",
        synthesis_link_reason="The unit remains in the main story because the proof and option tradeoffs must connect directly into the recommendation close.",
    ),
    "thesis-proof-close": SharedProofConsumerPolicy(
        option_id="thesis-proof-close",
        expected_non_appendix_sections=("Thesis", "Proof Spine", "Close"),
        claim_anchor_section_title="Thesis",
        bridge_section_titles=(),
        proof_section_title="Proof Spine",
        synthesis_anchor_section_title="Close",
        unit_id_prefix="thesis-proof-close-proof",
        unit_minimum=2,
        allowed_unit_roles=(SlideRole.EVIDENCE, SlideRole.COMPARISON, SlideRole.ANALYSIS),
        required_unit_roles=(),
        minimum_direct_evidence_units=1,
        minimum_synthesis_units=1,
        compat_mode=SharedProofCompatMode.NONE,
        claim_link_reason="The unit belongs to the thesis proof spine and directly supports the investor-facing thesis anchor.",
        synthesis_link_reason="The unit remains in the main story because the proof spine must flow directly into the closing ask.",
    ),
}


def shared_proof_consumer_policy(option_id: str | None) -> SharedProofConsumerPolicy | None:
    if option_id is None:
        return None
    return SHARED_PROOF_CONSUMER_POLICIES.get(str(option_id))


def is_shared_proof_consumer(option_id: str | None) -> bool:
    return shared_proof_consumer_policy(option_id) is not None


def canonical_shared_proof_fingerprint_key(key: str) -> str:
    if key in PROOF_FINGERPRINT_KEY_ALIASES:
        return PROOF_UNIT_REGISTRY_FINGERPRINT_KEY
    return key


def legacy_shared_proof_fingerprint_keys(keys: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    for key in keys:
        normalized = str(key or "").strip()
        if normalized in PROOF_FINGERPRINT_KEY_ALIASES and normalized not in ordered:
            ordered.append(normalized)
    return ordered


def is_legacy_manifest_migration_mode(option_id: str | None) -> bool:
    policy = shared_proof_consumer_policy(option_id)
    return policy is not None and policy.compat_mode == SharedProofCompatMode.LEGACY_MANIFEST_MIGRATION_ONLY


def legacy_manifest_surface_audit_rows() -> tuple[LegacyManifestSurfaceAuditRow, ...]:
    return (
        LegacyManifestSurfaceAuditRow(
            surface_id="shared-proof-fingerprint-alias",
            location="src/presentation_agent/non_pptx_modules/shared_proof_registry.py",
            classification=LegacyManifestSurfaceClassification.REQUIRED_BACKWARD_COMPAT,
            sunset_status=LegacyManifestSurfaceSunsetStatus.REQUIRED_FOR_ACTIVE_COMPAT,
            rationale=(
                "Legacy pipeline_state fingerprints can still carry `proof_module_manifest`, "
                "but the alias is now bounded to pipeline-state recollection and migration-time "
                "normalization rather than normal proof-artifact persistence."
            ),
        ),
        LegacyManifestSurfaceAuditRow(
            surface_id="manifest-to-registry-adapter",
            location="src/presentation_agent/non_pptx_modules/state_schemas.py",
            classification=LegacyManifestSurfaceClassification.REQUIRED_BACKWARD_COMPAT,
            sunset_status=LegacyManifestSurfaceSunsetStatus.REQUIRED_FOR_ACTIVE_COMPAT,
            rationale="Manifest-only workspaces still need an explicit upgrade path that can derive the canonical proof_unit_registry without losing provenance or changing semantics.",
        ),
        LegacyManifestSurfaceAuditRow(
            surface_id="manifest-schema-and-filename",
            location="schemas/compat/proof_module_manifest.schema.json",
            classification=LegacyManifestSurfaceClassification.COMPAT_ONLY_BUT_ISOLATED,
            sunset_status=LegacyManifestSurfaceSunsetStatus.COMPAT_ONLY_ISOLATED,
            rationale="The manifest schema now lives under an explicit compat-only schema path and the legacy artifact name is no longer advertised in the main state-schema inventory or default state-tool summaries.",
        ),
        LegacyManifestSurfaceAuditRow(
            surface_id="manifest-example-state",
            location="examples/compat-state/proof-module-manifest.json",
            classification=LegacyManifestSurfaceClassification.EXAMPLE_OR_FIXTURE_DEBT,
            sunset_status=LegacyManifestSurfaceSunsetStatus.COMPAT_ONLY_ISOLATED,
            rationale="The example is retained only as an explicit compat-only legacy sample outside the normal examples/state footprint.",
        ),
        LegacyManifestSurfaceAuditRow(
            surface_id="manifest-compat-test-fixtures",
            location="tests/test_proof_artifact_manifest_compat.py",
            classification=LegacyManifestSurfaceClassification.EXAMPLE_OR_FIXTURE_DEBT,
            sunset_status=LegacyManifestSurfaceSunsetStatus.COMPAT_ONLY_ISOLATED,
            rationale="Manifest-only and mixed-workspace fixtures now live in an explicit compat-only test module so migration coverage stays bounded away from normal-path integration tests.",
        ),
        LegacyManifestSurfaceAuditRow(
            surface_id="compat-runtime-warning",
            location="src/presentation_agent/compat/runtime_cli.py",
            classification=LegacyManifestSurfaceClassification.COMPAT_ONLY_BUT_ISOLATED,
            sunset_status=LegacyManifestSurfaceSunsetStatus.REQUIRED_FOR_ACTIVE_COMPAT,
            rationale="The compat runtime CLI is now limited to explicit proof-artifact doctor and sunset-rehearsal commands; it remains only as an active-compat migration surface and no longer forwards the full harness runtime.",
        ),
    )


def legacy_manifest_surface_summary() -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in legacy_manifest_surface_audit_rows():
        key = row.classification.value
        summary[key] = summary.get(key, 0) + 1
    return dict(sorted(summary.items()))


def legacy_manifest_surface_sunset_summary() -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in legacy_manifest_surface_audit_rows():
        key = row.sunset_status.value
        summary[key] = summary.get(key, 0) + 1
    return dict(sorted(summary.items()))


def proof_artifact_contract_regression_codes(
    option_id: str | None,
    *,
    proof_artifact_contract: Mapping[str, object] | None,
    proof_unit_registry_path: str | None,
    proof_module_manifest_path: str | None,
) -> list[str]:
    if shared_proof_consumer_policy(option_id) is None:
        return []

    failure_codes: list[str] = []
    registry_path = str(proof_unit_registry_path or "").strip() or None
    manifest_path = str(proof_module_manifest_path or "").strip() or None
    if registry_path is None:
        failure_codes.append("shared-proof-missing-proof-unit-registry-path")
    if manifest_path is not None:
        failure_codes.append("shared-proof-legacy-manifest-path-present")
    if not isinstance(proof_artifact_contract, Mapping):
        failure_codes.append("shared-proof-missing-proof-artifact-contract")
        return failure_codes

    if proof_artifact_contract.get("canonical_artifact") != PROOF_UNIT_REGISTRY_FINGERPRINT_KEY:
        failure_codes.append("shared-proof-canonical-artifact-drift")
    if proof_artifact_contract.get("contract_version") != PROOF_ARTIFACT_CONTRACT_VERSION:
        failure_codes.append("shared-proof-contract-version-drift")
    if proof_artifact_contract.get("normal_persistence_mode") != PROOF_ARTIFACT_NORMAL_PERSISTENCE_MODE:
        failure_codes.append("shared-proof-normal-persistence-mode-drift")
    if proof_artifact_contract.get("compat_mode") != "migration-only":
        failure_codes.append("shared-proof-compat-mode-drift")
    if proof_artifact_contract.get("compat_warning_scope") != PROOF_ARTIFACT_COMPAT_WARNING_SCOPE:
        failure_codes.append("shared-proof-compat-warning-scope-drift")
    if proof_artifact_contract.get("sunset_phase") != PROOF_ARTIFACT_SUNSET_PHASE:
        failure_codes.append("shared-proof-sunset-phase-drift")
    if proof_artifact_contract.get("fingerprint_key") != PROOF_UNIT_REGISTRY_FINGERPRINT_KEY:
        failure_codes.append("shared-proof-fingerprint-key-drift")
    fingerprint_aliases = proof_artifact_contract.get("fingerprint_aliases")
    if fingerprint_aliases != []:
        failure_codes.append("shared-proof-fingerprint-alias-drift")
    if proof_artifact_contract.get("fingerprint_alias_read_scope") != PROOF_FINGERPRINT_ALIAS_READ_SCOPE:
        failure_codes.append("shared-proof-fingerprint-alias-read-scope-drift")
    contract_registry_path = str(proof_artifact_contract.get("proof_unit_registry_path") or "").strip() or None
    if registry_path is not None and contract_registry_path != registry_path:
        failure_codes.append("shared-proof-contract-registry-path-mismatch")
    legacy_manifest_contract_path = str(proof_artifact_contract.get("legacy_manifest_path") or "").strip() or None
    if legacy_manifest_contract_path is not None:
        failure_codes.append("shared-proof-contract-legacy-manifest-path-present")
    return failure_codes


def proof_artifact_contract_payload(
    option_id: str | None,
    *,
    proof_unit_registry_path: str | None,
    proof_module_manifest_path: str | None,
    migration_status: str,
    doctor_report_path: str | None = None,
) -> dict[str, object] | None:
    policy = shared_proof_consumer_policy(option_id)
    if policy is None:
        return None
    migration_mode = (
        SharedProofCompatMode.LEGACY_MANIFEST_MIGRATION_ONLY.value
        if policy.compat_mode == SharedProofCompatMode.LEGACY_MANIFEST_MIGRATION_ONLY
        else PROOF_ARTIFACT_NORMAL_PERSISTENCE_MODE
    )
    legacy_manifest_status = (
        "not-present"
        if proof_module_manifest_path is None
        else "migration-input-retained"
        if migration_status in {"legacy-manifest-upgraded", "doctor-upgraded-manifest-only"}
        else "ignored-sidecar"
    )
    payload: dict[str, object] = {
        "contract_version": PROOF_ARTIFACT_CONTRACT_VERSION,
        "canonical_artifact": PROOF_UNIT_REGISTRY_FINGERPRINT_KEY,
        "normal_persistence_mode": PROOF_ARTIFACT_NORMAL_PERSISTENCE_MODE,
        "compat_mode": "migration-only",
        "compat_warning_scope": PROOF_ARTIFACT_COMPAT_WARNING_SCOPE,
        "migration_mode": migration_mode,
        "migration_status": migration_status,
        "sunset_phase": PROOF_ARTIFACT_SUNSET_PHASE,
        "fingerprint_key": PROOF_UNIT_REGISTRY_FINGERPRINT_KEY,
        "fingerprint_aliases": [],
        "fingerprint_alias_read_scope": PROOF_FINGERPRINT_ALIAS_READ_SCOPE,
        "proof_unit_registry_path": proof_unit_registry_path,
        "legacy_manifest_path": proof_module_manifest_path,
        "legacy_manifest_status": legacy_manifest_status,
    }
    if doctor_report_path is not None:
        payload["doctor_report_path"] = doctor_report_path
    return payload
