"""Doctor and migrator for shared proof-artifact retirement readiness."""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..non_pptx_modules.runtime_config import load_runtime_config
from ..non_pptx_modules.runtime_pipeline import resolve_runtime_workspace
from ..non_pptx_modules.shared_proof_registry import (
    PROOF_ARTIFACT_COMPAT_WARNING_SCOPE,
    PROOF_ARTIFACT_CONTRACT_VERSION,
    PROOF_FINGERPRINT_ALIAS_READ_SCOPE,
    PROOF_ARTIFACT_NORMAL_PERSISTENCE_MODE,
    PROOF_ARTIFACT_SUNSET_PHASE,
    PROOF_UNIT_REGISTRY_FINGERPRINT_KEY,
    ProofArtifactNormalizationMode,
    ProofArtifactWorkspaceMode,
    canonical_shared_proof_fingerprint_key,
    legacy_shared_proof_fingerprint_keys,
    legacy_manifest_surface_audit_rows,
    legacy_manifest_surface_summary,
    legacy_manifest_surface_sunset_summary,
    proof_artifact_contract_regression_codes,
    proof_artifact_contract_payload,
    shared_proof_consumer_policy,
)
from ..non_pptx_modules.state_schemas import (
    DEFAULT_STATE_FILENAMES,
    ProofArtifactFleetDiscoveryIssue,
    ProofArtifactFleetReport,
    ProofArtifactFleetWorkspaceReport,
    ProofArtifactDoctorReport,
    ProofArtifactDoctorSurface,
    ProofArtifactFingerprintContinuityRisk,
    ProofArtifactRemovalExitCriterion,
    ProofArtifactRemovalExitCriterionStatus,
    ProofArtifactRemovalRehearsalStatus,
    ProofArtifactSunsetBlockerCategory,
    ProofArtifactSunsetBlockerScope,
    ProofArtifactVNextBlocker,
    ProofArtifactVNextBlockerReport,
    ProofArtifactVNextWorkspaceReport,
    load_state_file,
    proof_unit_registry_from_proof_module_manifest,
    save_state_file,
)
from .executors import _proof_unit_registry_summary, collect_pipeline_fingerprints
from .orchestrator import PipelineOrchestrator
from .state_store import ArtifactEnvelope, FingerprintRecord, PipelineStateStore
from .stages import PipelineStage

RUNTIME_CONFIG_FILENAMES = frozenset({"runtime-config.yaml", "runtime-config.yml", "runtime-config.json"})
_WORKSPACE_DISCOVERY_EXCLUDED_DIRS = frozenset(
    {".git", ".hg", ".svn", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules"}
)
_FLEET_CLASSIFICATION_SELECTORS = frozenset(
    {
        ProofArtifactWorkspaceMode.NOT_APPLICABLE.value,
        ProofArtifactWorkspaceMode.REGISTRY_ONLY.value,
        ProofArtifactNormalizationMode.REGISTRY_ONLY_CLEAN.value,
        ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE.value,
        ProofArtifactWorkspaceMode.MANIFEST_ONLY.value,
        ProofArtifactWorkspaceMode.MIXED.value,
        ProofArtifactWorkspaceMode.MISSING.value,
    }
)


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _doctor_report_path(state_dir: Path) -> Path:
    return state_dir / DEFAULT_STATE_FILENAMES["proof_artifact_doctor_report"]


def _fleet_report_path(scan_root: Path, report_path: str | Path | None) -> Path:
    if report_path is None:
        return scan_root / DEFAULT_STATE_FILENAMES["proof_artifact_fleet_report"]
    candidate = Path(report_path)
    if candidate.is_absolute():
        return candidate
    return (scan_root / candidate).resolve()


def _vnext_blocker_report_path(scan_root: Path, report_path: str | Path | None) -> Path:
    if report_path is None:
        return scan_root / DEFAULT_STATE_FILENAMES["proof_artifact_vnext_blocker_report"]
    candidate = Path(report_path)
    if candidate.is_absolute():
        return candidate
    return (scan_root / candidate).resolve()


def _load_workflow_option(workflow_plan_path: Path) -> str | None:
    if not workflow_plan_path.is_file():
        return None
    workflow_plan = load_state_file(workflow_plan_path)
    workflow_option = str(getattr(workflow_plan, "workflow_option", "") or "").strip()
    return workflow_option or None


def _legacy_pipeline_state_fingerprint_aliases(store: PipelineStateStore) -> list[str]:
    if not store.pipeline_state_path.is_file():
        return []
    state = store.load_pipeline_state()
    return legacy_shared_proof_fingerprint_keys(record.key for record in state.fingerprints)


def _classify_workspace(
    *,
    direct_shared_proof_consumer: bool,
    registry_exists: bool,
    manifest_exists: bool,
) -> ProofArtifactWorkspaceMode:
    if not direct_shared_proof_consumer:
        return ProofArtifactWorkspaceMode.NOT_APPLICABLE
    if registry_exists and manifest_exists:
        return ProofArtifactWorkspaceMode.MIXED
    if manifest_exists:
        return ProofArtifactWorkspaceMode.MANIFEST_ONLY
    if registry_exists:
        return ProofArtifactWorkspaceMode.REGISTRY_ONLY
    return ProofArtifactWorkspaceMode.MISSING


def _normalization_classification(
    workspace_classification: ProofArtifactWorkspaceMode | str,
    fingerprint_aliases: list[str],
) -> ProofArtifactNormalizationMode:
    classification = ProofArtifactWorkspaceMode(str(workspace_classification))
    if classification == ProofArtifactWorkspaceMode.NOT_APPLICABLE:
        return ProofArtifactNormalizationMode.NOT_APPLICABLE
    if classification == ProofArtifactWorkspaceMode.MANIFEST_ONLY:
        return ProofArtifactNormalizationMode.MANIFEST_ONLY
    if classification == ProofArtifactWorkspaceMode.MIXED:
        return ProofArtifactNormalizationMode.MIXED
    if classification == ProofArtifactWorkspaceMode.MISSING:
        return ProofArtifactNormalizationMode.MISSING
    if fingerprint_aliases:
        return ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE
    return ProofArtifactNormalizationMode.REGISTRY_ONLY_CLEAN


def _classification_matches_selector(
    *,
    workspace_classification: str,
    normalization_classification: str,
    selected_classifications: set[str],
) -> bool:
    if not selected_classifications:
        return False
    return (
        workspace_classification in selected_classifications
        or normalization_classification in selected_classifications
    )


def _legacy_surface_audit() -> list[ProofArtifactDoctorSurface]:
    return [
        ProofArtifactDoctorSurface(
            surface_id=row.surface_id,
            location=row.location,
            classification=row.classification.value,
            sunset_status=row.sunset_status.value,
            rationale=row.rationale,
        )
        for row in legacy_manifest_surface_audit_rows()
    ]


def _load_content_plan_payload(content_plan_path: Path) -> dict[str, object] | None:
    if not content_plan_path.is_file():
        return None
    return json.loads(content_plan_path.read_text(encoding="utf-8"))


def _normalize_content_plan_artifact(
    *,
    workspace_root: Path,
    store: PipelineStateStore,
    workflow_option: str,
    proof_unit_registry_path: Path,
    doctor_report_path: Path,
    migration_status: str,
) -> bool:
    content_plan_path = store.artifact_path(PipelineStage.CONTENT_PLAN)
    payload = _load_content_plan_payload(content_plan_path)
    if payload is None:
        return False
    if str(payload.get("workflow_option") or "") != workflow_option:
        return False
    proof_unit_registry = load_state_file(proof_unit_registry_path)
    payload["proof_unit_registry_path"] = _display_path(proof_unit_registry_path, workspace_root)
    payload["proof_unit_registry_summary"] = _proof_unit_registry_summary(proof_unit_registry)
    payload.pop("proof_module_manifest_path", None)
    payload.pop("proof_module_manifest_summary", None)
    payload["proof_artifact_contract"] = proof_artifact_contract_payload(
        workflow_option,
        proof_unit_registry_path=_display_path(proof_unit_registry_path, workspace_root),
        proof_module_manifest_path=None,
        migration_status=migration_status,
        doctor_report_path=_display_path(doctor_report_path, workspace_root),
    )
    envelope = ArtifactEnvelope.model_validate(payload)
    store.save_artifact(envelope)
    return True


def _refresh_alias_active_registry_fingerprint(
    *,
    config,
    workspace,
    store: PipelineStateStore,
    orchestrator: PipelineOrchestrator,
) -> None:
    current_records = collect_pipeline_fingerprints(config, workspace)
    proof_record = next(
        (
            record
            for record in current_records
            if canonical_shared_proof_fingerprint_key(record.key) == PROOF_UNIT_REGISTRY_FINGERPRINT_KEY
        ),
        None,
    )
    if proof_record is None:
        return

    state = store.load_pipeline_state()
    replaced = False
    updated_records: list[FingerprintRecord] = []
    for record in state.fingerprints:
        if canonical_shared_proof_fingerprint_key(record.key) == PROOF_UNIT_REGISTRY_FINGERPRINT_KEY:
            updated_records.append(proof_record)
            replaced = True
            continue
        updated_records.append(record)
    if not replaced:
        updated_records.append(proof_record)

    normalized_records = orchestrator._normalize_fingerprints(updated_records)
    state.fingerprints = normalized_records
    state.last_input_fingerprint = orchestrator._combined_fingerprint(normalized_records)
    store.save_pipeline_state(state)


def inspect_or_normalize_proof_artifacts(
    config_path: str | Path,
    *,
    apply: bool = False,
) -> ProofArtifactDoctorReport:
    resolved_config_path = Path(config_path).resolve()
    config = load_runtime_config(resolved_config_path)
    workspace = resolve_runtime_workspace(config, resolved_config_path)
    store = PipelineStateStore(workspace.state_dir)
    orchestrator = PipelineOrchestrator(store, workspace_root=workspace.base_dir)
    workflow_option = _load_workflow_option(workspace.state_path("workflow_plan"))
    direct_shared_proof_consumer = shared_proof_consumer_policy(workflow_option) is not None
    proof_unit_registry_path = workspace.state_path("proof_unit_registry")
    proof_module_manifest_path = workspace.state_path("proof_module_manifest")
    content_plan_path = store.artifact_path(PipelineStage.CONTENT_PLAN)
    report_path = _doctor_report_path(workspace.state_dir)

    classification = _classify_workspace(
        direct_shared_proof_consumer=direct_shared_proof_consumer,
        registry_exists=proof_unit_registry_path.is_file(),
        manifest_exists=proof_module_manifest_path.is_file(),
    )
    initial_alias_keys = _legacy_pipeline_state_fingerprint_aliases(store)
    normalization_classification = _normalization_classification(classification, initial_alias_keys)
    migration_required = normalization_classification in {
        ProofArtifactNormalizationMode.MANIFEST_ONLY,
        ProofArtifactNormalizationMode.MIXED,
        ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE,
    }
    would_change: list[str] = []
    applied_changes: list[str] = []
    blockers: list[str] = []

    if normalization_classification == ProofArtifactNormalizationMode.MANIFEST_ONLY:
        would_change.extend(
            [
                "write-registry-from-manifest",
                "normalize-content-plan-proof-contract",
                "remove-legacy-manifest-sidecar",
                "refresh-canonical-proof-fingerprint",
            ]
        )
        migration_status = "would-upgrade-manifest-only"
    elif normalization_classification == ProofArtifactNormalizationMode.MIXED:
        would_change.extend(
            [
                "drop-legacy-manifest-sidecar",
                "normalize-content-plan-proof-contract",
                "refresh-canonical-proof-fingerprint",
            ]
        )
        migration_status = "would-normalize-mixed"
    elif normalization_classification == ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE:
        would_change.append("refresh-canonical-proof-fingerprint")
        blockers.append("legacy-pipeline-state-fingerprint-alias-active")
        migration_status = "legacy-alias-read-normalization-pending"
    elif normalization_classification == ProofArtifactNormalizationMode.REGISTRY_ONLY_CLEAN:
        migration_status = "already-registry-first"
    elif classification == ProofArtifactWorkspaceMode.MISSING:
        blockers.append("shared-proof-consumer-missing-proof-artifact")
        migration_status = "missing-proof-artifact"
    else:
        migration_status = "not-applicable"

    if apply and direct_shared_proof_consumer:
        if normalization_classification == ProofArtifactNormalizationMode.MANIFEST_ONLY:
            manifest = load_state_file(proof_module_manifest_path)
            proof_unit_registry = proof_unit_registry_from_proof_module_manifest(manifest)
            save_state_file(proof_unit_registry, proof_unit_registry_path)
            applied_changes.append("write-registry-from-manifest")
            if _normalize_content_plan_artifact(
                workspace_root=workspace.base_dir,
                store=store,
                workflow_option=workflow_option or "",
                proof_unit_registry_path=proof_unit_registry_path,
                doctor_report_path=report_path,
                migration_status="doctor-upgraded-manifest-only",
            ):
                applied_changes.append("normalize-content-plan-proof-contract")
            if proof_module_manifest_path.exists():
                proof_module_manifest_path.unlink()
                applied_changes.append("remove-legacy-manifest-sidecar")
            orchestrator.refresh_fingerprints(collect_pipeline_fingerprints(config, workspace))
            applied_changes.append("refresh-canonical-proof-fingerprint")
            classification = ProofArtifactWorkspaceMode.REGISTRY_ONLY
            migration_status = "doctor-upgraded-manifest-only"
        elif normalization_classification == ProofArtifactNormalizationMode.MIXED:
            if _normalize_content_plan_artifact(
                workspace_root=workspace.base_dir,
                store=store,
                workflow_option=workflow_option or "",
                proof_unit_registry_path=proof_unit_registry_path,
                doctor_report_path=report_path,
                migration_status="doctor-normalized-mixed",
            ):
                applied_changes.append("normalize-content-plan-proof-contract")
            if proof_module_manifest_path.exists():
                proof_module_manifest_path.unlink()
                applied_changes.append("remove-legacy-manifest-sidecar")
            orchestrator.refresh_fingerprints(collect_pipeline_fingerprints(config, workspace))
            applied_changes.append("refresh-canonical-proof-fingerprint")
            classification = ProofArtifactWorkspaceMode.REGISTRY_ONLY
            migration_status = "doctor-normalized-mixed"
        elif normalization_classification == ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE:
            _refresh_alias_active_registry_fingerprint(
                config=config,
                workspace=workspace,
                store=store,
                orchestrator=orchestrator,
            )
            applied_changes.append("refresh-canonical-proof-fingerprint")
            migration_status = "doctor-refreshed-registry-alias-state"

    final_alias_keys = _legacy_pipeline_state_fingerprint_aliases(store)
    normalization_classification = _normalization_classification(classification, final_alias_keys)
    migration_required = normalization_classification in {
        ProofArtifactNormalizationMode.MANIFEST_ONLY,
        ProofArtifactNormalizationMode.MIXED,
        ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE,
    }
    blockers = [blocker for blocker in blockers if blocker != "legacy-pipeline-state-fingerprint-alias-active"]
    if normalization_classification == ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE:
        if migration_status == "already-registry-first":
            migration_status = "legacy-alias-read-normalization-pending"
        if "refresh-canonical-proof-fingerprint" not in would_change:
            would_change.append("refresh-canonical-proof-fingerprint")
        blockers.append("legacy-pipeline-state-fingerprint-alias-active")

    report = ProofArtifactDoctorReport(
        workspace_root=workspace.base_dir.as_posix(),
        config_path=resolved_config_path.as_posix(),
        workflow_option=workflow_option,
        direct_shared_proof_consumer=direct_shared_proof_consumer,
        canonical_artifact=PROOF_UNIT_REGISTRY_FINGERPRINT_KEY,
        proof_artifact_contract_version=PROOF_ARTIFACT_CONTRACT_VERSION,
        normal_persistence_mode=PROOF_ARTIFACT_NORMAL_PERSISTENCE_MODE,
        compat_mode="migration-only",
        compat_warning_scope=PROOF_ARTIFACT_COMPAT_WARNING_SCOPE,
        sunset_phase=PROOF_ARTIFACT_SUNSET_PHASE,
        workspace_classification=classification.value,
        normalization_classification=normalization_classification.value,
        migration_required=migration_required,
        migration_status=migration_status,
        dry_run=not apply,
        proof_unit_registry_path=_display_path(proof_unit_registry_path, workspace.base_dir)
        if proof_unit_registry_path.exists()
        else None,
        proof_module_manifest_path=_display_path(proof_module_manifest_path, workspace.base_dir)
        if proof_module_manifest_path.exists()
        else None,
        content_plan_path=_display_path(content_plan_path, workspace.base_dir) if content_plan_path.exists() else None,
        pipeline_state_path=_display_path(store.pipeline_state_path, workspace.base_dir)
        if store.pipeline_state_path.exists()
        else None,
        fingerprint_key=canonical_shared_proof_fingerprint_key(PROOF_UNIT_REGISTRY_FINGERPRINT_KEY),
        fingerprint_aliases=final_alias_keys,
        fingerprint_alias_read_scope=PROOF_FINGERPRINT_ALIAS_READ_SCOPE,
        legacy_surface_audit=_legacy_surface_audit(),
        would_change=would_change,
        applied_changes=applied_changes,
        blockers=blockers,
    )
    save_state_file(report, report_path)
    return report


def _resolved_scan_root(scan_root: str | Path) -> tuple[Path, list[Path]]:
    candidate = Path(scan_root).resolve()
    if not candidate.exists():
        raise FileNotFoundError(candidate)
    if candidate.is_file():
        return candidate.parent, [candidate]
    return candidate, []


def _discover_runtime_config_paths(scan_root: Path, explicit_configs: list[Path]) -> tuple[list[Path], list[ProofArtifactFleetDiscoveryIssue]]:
    if explicit_configs:
        candidates = [config.resolve() for config in explicit_configs]
    else:
        candidates = []
        for current_root, dirnames, filenames in os.walk(scan_root):
            dirnames[:] = [name for name in dirnames if name not in _WORKSPACE_DISCOVERY_EXCLUDED_DIRS]
            for filename in sorted(filenames):
                if filename in RUNTIME_CONFIG_FILENAMES:
                    candidates.append((Path(current_root) / filename).resolve())

    issues: list[ProofArtifactFleetDiscoveryIssue] = []
    discovered: dict[Path, Path] = {}
    for config_path in sorted(candidates):
        try:
            config = load_runtime_config(config_path)
            workspace = resolve_runtime_workspace(config, config_path)
        except Exception as exc:
            issues.append(
                ProofArtifactFleetDiscoveryIssue(
                    path=config_path.as_posix(),
                    issue_code="invalid-runtime-config",
                    detail=str(exc),
                )
            )
            continue
        workspace_root = workspace.base_dir.resolve()
        previous = discovered.get(workspace_root)
        if previous is not None:
            issues.append(
                ProofArtifactFleetDiscoveryIssue(
                    path=config_path.as_posix(),
                    issue_code="duplicate-workspace-root",
                    detail=f"resolved workspace root duplicates {previous.as_posix()}",
                )
            )
            continue
        discovered[workspace_root] = config_path
    return [discovered[key] for key in sorted(discovered)], issues


def _selected_classifications(
    workspace_classifications: list[str] | None,
    *,
    apply: bool,
) -> list[str]:
    if workspace_classifications:
        selected = [item.strip() for item in workspace_classifications if item.strip()]
    elif apply:
        selected = [
            ProofArtifactWorkspaceMode.MANIFEST_ONLY.value,
            ProofArtifactWorkspaceMode.MIXED.value,
            ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE.value,
        ]
    else:
        selected = []
    ordered = sorted(dict.fromkeys(selected))
    invalid = [item for item in ordered if item not in _FLEET_CLASSIFICATION_SELECTORS]
    if invalid:
        raise ValueError(f"invalid proof-artifact fleet classification selectors: {invalid}")
    return ordered


def _fingerprint_continuity_status(
    initial_normalization_classification: str,
    final_normalization_classification: str,
    *,
    apply: bool,
) -> str:
    if final_normalization_classification == ProofArtifactNormalizationMode.NOT_APPLICABLE.value:
        return "not-applicable"
    if final_normalization_classification == ProofArtifactNormalizationMode.MISSING.value:
        return "missing-proof-artifact"
    if initial_normalization_classification in {
        ProofArtifactNormalizationMode.MANIFEST_ONLY.value,
        ProofArtifactNormalizationMode.MIXED.value,
    }:
        if apply and final_normalization_classification in {
            ProofArtifactNormalizationMode.REGISTRY_ONLY_CLEAN.value,
            ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE.value,
        }:
            return "normalized-semantic-fingerprint"
        return "pending-normalization"
    if initial_normalization_classification == ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE.value:
        if apply and final_normalization_classification == ProofArtifactNormalizationMode.REGISTRY_ONLY_CLEAN.value:
            return "normalized-alias-refresh"
        return "alias-refresh-pending"
    return "registry-stable"


def _sunset_enforcement_codes(workspace_root: Path, report: ProofArtifactDoctorReport) -> list[str]:
    if not report.direct_shared_proof_consumer:
        return []

    failure_codes: list[str] = []
    if report.workspace_classification != ProofArtifactWorkspaceMode.REGISTRY_ONLY.value:
        failure_codes.append("shared-proof-direct-consumer-not-registry-only")

    if not report.content_plan_path:
        return failure_codes
    content_plan_path = workspace_root / report.content_plan_path
    payload = _load_content_plan_payload(content_plan_path)
    if payload is None:
        failure_codes.append("shared-proof-content-plan-missing")
        return list(dict.fromkeys(failure_codes))

    failure_codes.extend(
        proof_artifact_contract_regression_codes(
            report.workflow_option,
            proof_artifact_contract=payload.get("proof_artifact_contract")
            if isinstance(payload.get("proof_artifact_contract"), dict)
            else None,
            proof_unit_registry_path=payload.get("proof_unit_registry_path")
            if isinstance(payload.get("proof_unit_registry_path"), str)
            else None,
            proof_module_manifest_path=payload.get("proof_module_manifest_path")
            if isinstance(payload.get("proof_module_manifest_path"), str)
            else None,
        )
    )
    return list(dict.fromkeys(failure_codes))


def _fingerprint_continuity_risk(
    *,
    normalization_classification: str,
    workspace_classification: str,
    fingerprint_continuity_status: str,
) -> ProofArtifactFingerprintContinuityRisk:
    if workspace_classification in {
        ProofArtifactWorkspaceMode.MANIFEST_ONLY.value,
        ProofArtifactWorkspaceMode.MIXED.value,
    } or fingerprint_continuity_status in {"pending-normalization", "normalized-semantic-fingerprint"}:
        return ProofArtifactFingerprintContinuityRisk.SEMANTIC_NORMALIZATION_REQUIRED
    if normalization_classification == ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE.value:
        return ProofArtifactFingerprintContinuityRisk.LEGACY_ALIAS_STILL_REQUIRED
    if workspace_classification == ProofArtifactWorkspaceMode.MISSING.value:
        return ProofArtifactFingerprintContinuityRisk.MISSING_CANONICAL_PROOF_ARTIFACT
    if workspace_classification == ProofArtifactWorkspaceMode.NOT_APPLICABLE.value:
        return ProofArtifactFingerprintContinuityRisk.NOT_APPLICABLE
    return ProofArtifactFingerprintContinuityRisk.NONE


def _workspace_classification_blocker(
    workspace_report: ProofArtifactFleetWorkspaceReport,
) -> ProofArtifactVNextBlocker | None:
    category: ProofArtifactSunsetBlockerCategory | None = None
    blocker_code: str | None = None
    detail: str | None = None
    suggested_action: str | None = None

    if workspace_report.workspace_classification == ProofArtifactWorkspaceMode.MANIFEST_ONLY.value:
        category = ProofArtifactSunsetBlockerCategory.WORKSPACE_MANIFEST_ONLY
        blocker_code = "workspace-manifest-only"
        detail = (
            "The workspace still depends on state/proof-module-manifest.json and would not survive a manifest-free release."
        )
        suggested_action = (
            "Run doctor-proof-artifact-fleet --apply --classification manifest-only, then rerun the vNext rehearsal."
        )
    elif workspace_report.workspace_classification == ProofArtifactWorkspaceMode.MIXED.value:
        category = ProofArtifactSunsetBlockerCategory.WORKSPACE_MIXED_ARTIFACTS
        blocker_code = "workspace-mixed-artifacts"
        detail = (
            "The workspace still carries both proof-unit registry and legacy manifest artifacts, so removal would be ambiguous."
        )
        suggested_action = (
            "Run doctor-proof-artifact-fleet --apply --classification mixed, then rerun the vNext rehearsal."
        )
    elif workspace_report.workspace_classification == ProofArtifactWorkspaceMode.MISSING.value:
        category = ProofArtifactSunsetBlockerCategory.WORKSPACE_MISSING_REGISTRY_ARTIFACT
        blocker_code = "workspace-missing-proof-artifact"
        detail = "The direct shared-proof workspace is missing a canonical proof_unit_registry artifact."
        suggested_action = (
            "Regenerate or reapprove CONTENT_PLAN so the canonical proof-unit registry is persisted before removal."
        )

    if category is None or blocker_code is None or detail is None or suggested_action is None:
        return None
    return ProofArtifactVNextBlocker(
        scope_kind=ProofArtifactSunsetBlockerScope.WORKSPACE,
        scope_ref=workspace_report.workspace_root,
        workflow_option=workspace_report.workflow_option,
        blocker_category=category,
        blocker_code=blocker_code,
        detail=detail,
        suggested_action=suggested_action,
        fingerprint_continuity_risk=_fingerprint_continuity_risk(
            normalization_classification=workspace_report.normalization_classification,
            workspace_classification=workspace_report.workspace_classification,
            fingerprint_continuity_status=workspace_report.fingerprint_continuity_status,
        ),
    )


def _workspace_enforcement_blockers(
    workspace_report: ProofArtifactFleetWorkspaceReport,
) -> list[ProofArtifactVNextBlocker]:
    blockers: list[ProofArtifactVNextBlocker] = []
    continuity_risk = _fingerprint_continuity_risk(
        normalization_classification=workspace_report.normalization_classification,
        workspace_classification=workspace_report.workspace_classification,
        fingerprint_continuity_status=workspace_report.fingerprint_continuity_status,
    )
    for code in workspace_report.sunset_enforcement_codes:
        if code == "shared-proof-direct-consumer-not-registry-only":
            continue
        blockers.append(
            ProofArtifactVNextBlocker(
                scope_kind=ProofArtifactSunsetBlockerScope.WORKSPACE,
                scope_ref=workspace_report.workspace_root,
                workflow_option=workspace_report.workflow_option,
                blocker_category=ProofArtifactSunsetBlockerCategory.NORMAL_PATH_MANIFEST_REGRESSION,
                blocker_code=code,
                detail=(
                    "The approved shared-proof content-plan contract still depends on legacy or malformed manifest-era state."
                ),
                suggested_action=(
                    "Repair the approved CONTENT_PLAN proof-artifact contract so it stays registry-first, then rerun the vNext rehearsal."
                ),
                fingerprint_continuity_risk=continuity_risk,
            )
        )
    return blockers


def _workspace_alias_blockers(
    workspace_report: ProofArtifactFleetWorkspaceReport,
) -> list[ProofArtifactVNextBlocker]:
    if not workspace_report.direct_shared_proof_consumer:
        return []
    if (
        workspace_report.normalization_classification
        != ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE.value
    ):
        return []
    alias_keys = list(workspace_report.fingerprint_aliases)
    if not alias_keys:
        return []
    return [
        ProofArtifactVNextBlocker(
            scope_kind=ProofArtifactSunsetBlockerScope.WORKSPACE,
            scope_ref=workspace_report.workspace_root,
            workflow_option=workspace_report.workflow_option,
            blocker_category=ProofArtifactSunsetBlockerCategory.LEGACY_FINGERPRINT_ALIAS_DEPENDENCY,
            blocker_code="legacy-pipeline-state-fingerprint-alias-active",
            detail=(
                "The workspace is registry-first, but its persisted pipeline_state still carries "
                f"legacy proof fingerprint alias keys: {', '.join(alias_keys)}."
            ),
            suggested_action=(
                "Refresh canonical proof fingerprints with doctor-proof-artifacts --apply or "
                "doctor-proof-artifact-fleet --apply --classification registry-only-alias-active "
                "so recollection no longer depends on legacy alias keys."
            ),
            fingerprint_continuity_risk=ProofArtifactFingerprintContinuityRisk.LEGACY_ALIAS_STILL_REQUIRED,
        )
    ]


def _repo_surface_blockers() -> list[ProofArtifactVNextBlocker]:
    blockers: list[ProofArtifactVNextBlocker] = []
    for row in legacy_manifest_surface_audit_rows():
        if row.sunset_status.value != "still-blocking":
            continue
        if row.surface_id == "manifest-schema-and-filename":
            blockers.append(
                ProofArtifactVNextBlocker(
                    scope_kind=ProofArtifactSunsetBlockerScope.REPO_SURFACE,
                    scope_ref=row.location,
                    blocker_category=ProofArtifactSunsetBlockerCategory.COMPAT_SCHEMA_OR_EXAMPLE_DEPENDENCY,
                    blocker_code=row.surface_id,
                    detail=row.rationale,
                    suggested_action=(
                        "Delete or archive the legacy manifest schema/example in the breaking removal release once migration coverage is no longer needed."
                    ),
                    fingerprint_continuity_risk=ProofArtifactFingerprintContinuityRisk.COMPAT_SURFACE_STILL_REQUIRED,
                )
            )
        elif row.surface_id == "compat-runtime-warning":
            blockers.append(
                ProofArtifactVNextBlocker(
                    scope_kind=ProofArtifactSunsetBlockerScope.REPO_SURFACE,
                    scope_ref=row.location,
                    blocker_category=ProofArtifactSunsetBlockerCategory.COMPAT_CLI_RUNTIME_DEPENDENCY,
                    blocker_code=row.surface_id,
                    detail=row.rationale,
                    suggested_action=(
                        "Remove the explicit compat CLI/runtime entrypoint in the breaking manifest-removal release."
                    ),
                    fingerprint_continuity_risk=ProofArtifactFingerprintContinuityRisk.COMPAT_SURFACE_STILL_REQUIRED,
                )
            )
    return blockers


def _discovery_issue_blockers(
    discovery_issues: list[ProofArtifactFleetDiscoveryIssue],
) -> list[ProofArtifactVNextBlocker]:
    return [
        ProofArtifactVNextBlocker(
            scope_kind=ProofArtifactSunsetBlockerScope.FLEET,
            scope_ref=issue.path,
            blocker_category=ProofArtifactSunsetBlockerCategory.UNKNOWN_OR_UNCLASSIFIED,
            blocker_code=issue.issue_code,
            detail=issue.detail,
            suggested_action="Fix runtime-config discovery issues before trusting the vNext removal rehearsal result.",
            fingerprint_continuity_risk=ProofArtifactFingerprintContinuityRisk.NOT_APPLICABLE,
        )
        for issue in discovery_issues
    ]


def _rehearsal_status(
    *,
    discovered_workspace_count: int,
    discovery_errors: list[ProofArtifactFleetDiscoveryIssue],
    blocker_counts_by_category: dict[str, int],
) -> ProofArtifactRemovalRehearsalStatus:
    if discovery_errors:
        return ProofArtifactRemovalRehearsalStatus.BLOCKED_BY_DISCOVERY_ERRORS
    if discovered_workspace_count == 0:
        return ProofArtifactRemovalRehearsalStatus.BLOCKED_BY_EMPTY_SCOPE
    if blocker_counts_by_category.get(ProofArtifactSunsetBlockerCategory.NORMAL_PATH_MANIFEST_REGRESSION.value, 0):
        return ProofArtifactRemovalRehearsalStatus.BLOCKED_BY_NORMAL_PATH_REGRESSION
    if any(
        blocker_counts_by_category.get(category.value, 0)
        for category in (
            ProofArtifactSunsetBlockerCategory.WORKSPACE_MANIFEST_ONLY,
            ProofArtifactSunsetBlockerCategory.WORKSPACE_MIXED_ARTIFACTS,
            ProofArtifactSunsetBlockerCategory.WORKSPACE_MISSING_REGISTRY_ARTIFACT,
        )
    ):
        return ProofArtifactRemovalRehearsalStatus.BLOCKED_BY_WORKSPACE_BLOCKERS
    if blocker_counts_by_category.get(ProofArtifactSunsetBlockerCategory.LEGACY_FINGERPRINT_ALIAS_DEPENDENCY.value, 0):
        return ProofArtifactRemovalRehearsalStatus.BLOCKED_BY_ALIAS_ACTIVE_WORKSPACE_STATE
    if blocker_counts_by_category:
        return ProofArtifactRemovalRehearsalStatus.BLOCKED_BY_COMPAT_SURFACE_DEBT
    return ProofArtifactRemovalRehearsalStatus.READY_FOR_VNEXT_MANIFEST_REMOVAL


def _recommended_rehearsal_next_step(
    status: ProofArtifactRemovalRehearsalStatus,
) -> str:
    if status == ProofArtifactRemovalRehearsalStatus.BLOCKED_BY_DISCOVERY_ERRORS:
        return "Fix runtime-config discovery errors, then rerun the sunset rehearsal on the intended workspace root."
    if status == ProofArtifactRemovalRehearsalStatus.BLOCKED_BY_EMPTY_SCOPE:
        return "Point the rehearsal at a real runtime workspace root or config file before deciding whether manifest removal is safe."
    if status == ProofArtifactRemovalRehearsalStatus.BLOCKED_BY_NORMAL_PATH_REGRESSION:
        return "Repair registry-first content-plan regressions before planning any manifest-removal release."
    if status == ProofArtifactRemovalRehearsalStatus.BLOCKED_BY_WORKSPACE_BLOCKERS:
        return "Normalize remaining manifest-only or mixed workspaces first, then rerun the sunset rehearsal."
    if status == ProofArtifactRemovalRehearsalStatus.BLOCKED_BY_ALIAS_ACTIVE_WORKSPACE_STATE:
        return "Refresh canonical proof fingerprints for alias-active registry-only workspaces, then rerun the sunset rehearsal."
    if status == ProofArtifactRemovalRehearsalStatus.BLOCKED_BY_COMPAT_SURFACE_DEBT:
        return "The runtime workspaces are already registry-first; the remaining blockers are repo compat surfaces that still need a coordinated breaking-change cleanup."
    return "The audited scope is ready for a manifest-removal breaking release."


def _build_exit_criteria(
    *,
    discovered_workspace_count: int,
    discovery_errors: list[ProofArtifactFleetDiscoveryIssue],
    blocker_counts_by_category: dict[str, int],
) -> list[ProofArtifactRemovalExitCriterion]:
    compat_schema_or_example_blocker_count = blocker_counts_by_category.get(
        ProofArtifactSunsetBlockerCategory.COMPAT_SCHEMA_OR_EXAMPLE_DEPENDENCY.value,
        0,
    )
    compat_cli_runtime_blocker_count = blocker_counts_by_category.get(
        ProofArtifactSunsetBlockerCategory.COMPAT_CLI_RUNTIME_DEPENDENCY.value,
        0,
    )

    def criterion(
        criterion_id: str,
        description: str,
        *,
        categories: list[ProofArtifactSunsetBlockerCategory],
        passed: bool,
        detail: str,
    ) -> ProofArtifactRemovalExitCriterion:
        blocker_count = sum(blocker_counts_by_category.get(category.value, 0) for category in categories)
        return ProofArtifactRemovalExitCriterion(
            criterion_id=criterion_id,
            description=description,
            status=(
                ProofArtifactRemovalExitCriterionStatus.PASS
                if passed
                else ProofArtifactRemovalExitCriterionStatus.FAIL
            ),
            blocker_categories=categories,
            blocker_count=blocker_count,
            detail=detail,
        )

    return [
        criterion(
            "non-empty-audited-scope",
            "The rehearsal scans at least one discovered runtime workspace.",
            categories=[ProofArtifactSunsetBlockerCategory.UNKNOWN_OR_UNCLASSIFIED],
            passed=discovered_workspace_count > 0,
            detail=(
                f"Discovered {discovered_workspace_count} workspace(s)."
                if discovered_workspace_count > 0
                else "No runtime workspaces were discovered under the selected rehearsal scope."
            ),
        ),
        criterion(
            "no-discovery-errors",
            "Runtime-config discovery does not leave unresolved scan errors.",
            categories=[ProofArtifactSunsetBlockerCategory.UNKNOWN_OR_UNCLASSIFIED],
            passed=not discovery_errors,
            detail=(
                "No runtime-config discovery errors remain."
                if not discovery_errors
                else f"{len(discovery_errors)} runtime-config discovery error(s) still block a trustworthy removal rehearsal."
            ),
        ),
        criterion(
            "no-direct-consumer-manifest-only-workspaces",
            "No direct shared-proof consumer workspace remains manifest-only.",
            categories=[ProofArtifactSunsetBlockerCategory.WORKSPACE_MANIFEST_ONLY],
            passed=blocker_counts_by_category.get(ProofArtifactSunsetBlockerCategory.WORKSPACE_MANIFEST_ONLY.value, 0) == 0,
            detail="Manifest-only direct-consumer workspaces must be normalized before breaking removal.",
        ),
        criterion(
            "no-direct-consumer-mixed-workspaces",
            "No direct shared-proof consumer workspace remains in a mixed registry+manifest state.",
            categories=[ProofArtifactSunsetBlockerCategory.WORKSPACE_MIXED_ARTIFACTS],
            passed=blocker_counts_by_category.get(ProofArtifactSunsetBlockerCategory.WORKSPACE_MIXED_ARTIFACTS.value, 0) == 0,
            detail="Mixed workspaces hide ambiguity about which artifact is canonical during removal.",
        ),
        criterion(
            "no-direct-consumer-missing-proof-artifacts",
            "No direct shared-proof consumer workspace is missing its canonical proof-unit registry.",
            categories=[ProofArtifactSunsetBlockerCategory.WORKSPACE_MISSING_REGISTRY_ARTIFACT],
            passed=blocker_counts_by_category.get(
                ProofArtifactSunsetBlockerCategory.WORKSPACE_MISSING_REGISTRY_ARTIFACT.value,
                0,
            )
            == 0,
            detail="Missing proof artifacts would fail early under strict registry-only removal mode.",
        ),
        criterion(
            "no-direct-consumer-normal-path-manifest-regressions",
            "Approved direct-consumer content plans stay registry-first with no manifest regressions.",
            categories=[ProofArtifactSunsetBlockerCategory.NORMAL_PATH_MANIFEST_REGRESSION],
            passed=blocker_counts_by_category.get(
                ProofArtifactSunsetBlockerCategory.NORMAL_PATH_MANIFEST_REGRESSION.value,
                0,
            )
            == 0,
            detail="Current registry-first steady-state must remain clean before the repo can remove legacy manifest behavior.",
        ),
        criterion(
            "no-legacy-fingerprint-alias-dependency",
            "No discovered registry-only workspace still depends on proof_module_manifest alias keys in pipeline_state.",
            categories=[ProofArtifactSunsetBlockerCategory.LEGACY_FINGERPRINT_ALIAS_DEPENDENCY],
            passed=blocker_counts_by_category.get(
                ProofArtifactSunsetBlockerCategory.LEGACY_FINGERPRINT_ALIAS_DEPENDENCY.value,
                0,
            )
            == 0,
            detail=(
                "No audited registry-only workspace currently persists legacy proof fingerprint alias keys."
                if blocker_counts_by_category.get(
                    ProofArtifactSunsetBlockerCategory.LEGACY_FINGERPRINT_ALIAS_DEPENDENCY.value,
                    0,
                )
                == 0
                else "One or more audited registry-only workspaces still persist legacy proof fingerprint alias keys in pipeline_state."
            ),
        ),
        criterion(
            "no-compat-schema-or-example-dependency",
            "Legacy manifest schema/example files are no longer part of the normal repo surface.",
            categories=[ProofArtifactSunsetBlockerCategory.COMPAT_SCHEMA_OR_EXAMPLE_DEPENDENCY],
            passed=compat_schema_or_example_blocker_count == 0,
            detail=(
                "Compat manifest schema/example surfaces are isolated from the normal repo surface."
                if compat_schema_or_example_blocker_count == 0
                else "Manifest schemas/examples still present a removal blocker until the breaking cleanup lands."
            ),
        ),
        criterion(
            "no-compat-test-or-fixture-dependency",
            "Manifest-era migration tests and fixtures have been retired or moved behind an archived compat layer.",
            categories=[ProofArtifactSunsetBlockerCategory.COMPAT_TEST_OR_FIXTURE_DEPENDENCY],
            passed=blocker_counts_by_category.get(
                ProofArtifactSunsetBlockerCategory.COMPAT_TEST_OR_FIXTURE_DEPENDENCY.value,
                0,
            )
            == 0,
            detail="Focused migration tests still reference manifest-era state by design.",
        ),
        criterion(
            "no-compat-cli-runtime-dependency",
            "Explicit compat CLI/runtime manifest surfaces are gone from the breaking-release target.",
            categories=[ProofArtifactSunsetBlockerCategory.COMPAT_CLI_RUNTIME_DEPENDENCY],
            passed=compat_cli_runtime_blocker_count == 0,
            detail=(
                "Compat CLI/runtime surfaces are quarantined to explicit active-compat doctor and rehearsal commands."
                if compat_cli_runtime_blocker_count == 0
                else "Compat-only runtime surfaces still exist and must be removed during the actual breaking release."
            ),
        ),
    ]


def inspect_or_normalize_proof_artifact_fleet(
    scan_root: str | Path,
    *,
    apply: bool = False,
    workspace_classifications: list[str] | None = None,
    report_path: str | Path | None = None,
) -> ProofArtifactFleetReport:
    resolved_scan_root, explicit_configs = _resolved_scan_root(scan_root)
    discovered_configs, discovery_issues = _discover_runtime_config_paths(resolved_scan_root, explicit_configs)
    selected_classifications = _selected_classifications(workspace_classifications, apply=apply)

    workspace_reports: list[ProofArtifactFleetWorkspaceReport] = []
    classification_counts: dict[str, int] = {}
    normalization_classification_counts: dict[str, int] = {}
    continuity_counts: dict[str, int] = {}
    migration_required_count = 0
    migration_applied_count = 0
    direct_shared_proof_consumer_count = 0

    for config_path in discovered_configs:
        initial_report = inspect_or_normalize_proof_artifacts(config_path, apply=False)
        selected_for_apply = apply and _classification_matches_selector(
            workspace_classification=initial_report.workspace_classification,
            normalization_classification=initial_report.normalization_classification,
            selected_classifications=set(selected_classifications),
        )
        final_report = (
            inspect_or_normalize_proof_artifacts(config_path, apply=True)
            if selected_for_apply
            else initial_report
        )
        workspace_root = Path(final_report.workspace_root).resolve()
        continuity_status = _fingerprint_continuity_status(
            initial_report.normalization_classification,
            final_report.normalization_classification,
            apply=selected_for_apply,
        )
        enforcement_codes = _sunset_enforcement_codes(workspace_root, final_report)
        doctor_report_path = _doctor_report_path(workspace_root / "state")

        workspace_reports.append(
            ProofArtifactFleetWorkspaceReport(
                workspace_root=_display_path(workspace_root, resolved_scan_root),
                config_path=_display_path(config_path, resolved_scan_root),
                workflow_option=final_report.workflow_option,
                direct_shared_proof_consumer=final_report.direct_shared_proof_consumer,
                workspace_classification=final_report.workspace_classification,
                normalization_classification=final_report.normalization_classification,
                selected_for_apply=selected_for_apply,
                migration_required=final_report.migration_required,
                migration_status=final_report.migration_status,
                doctor_report_path=_display_path(doctor_report_path, resolved_scan_root)
                if doctor_report_path.exists()
                else None,
                proof_unit_registry_path=final_report.proof_unit_registry_path,
                proof_module_manifest_path=final_report.proof_module_manifest_path,
                content_plan_path=final_report.content_plan_path,
                pipeline_state_path=final_report.pipeline_state_path,
                fingerprint_key=final_report.fingerprint_key,
                fingerprint_aliases=list(final_report.fingerprint_aliases),
                fingerprint_alias_read_scope=final_report.fingerprint_alias_read_scope,
                fingerprint_continuity_status=continuity_status,
                sunset_enforcement_passed=not enforcement_codes,
                sunset_enforcement_codes=enforcement_codes,
                would_change=list(initial_report.would_change),
                applied_changes=list(final_report.applied_changes),
                blockers=list(final_report.blockers),
            )
        )

        classification_counts[final_report.workspace_classification] = (
            classification_counts.get(final_report.workspace_classification, 0) + 1
        )
        normalization_classification_counts[final_report.normalization_classification] = (
            normalization_classification_counts.get(final_report.normalization_classification, 0) + 1
        )
        continuity_counts[continuity_status] = continuity_counts.get(continuity_status, 0) + 1
        if final_report.migration_required:
            migration_required_count += 1
        if selected_for_apply and final_report.applied_changes:
            migration_applied_count += 1
        if final_report.direct_shared_proof_consumer:
            direct_shared_proof_consumer_count += 1

    audit_rows = _legacy_surface_audit()
    compat_debt_summary = legacy_manifest_surface_summary()
    repo_surface_status_counts = legacy_manifest_surface_sunset_summary()
    normal_path_debt_present = any(surface.classification == "normal_path_debt" for surface in audit_rows)
    direct_consumer_normal_path_debt = sorted(
        {
            code
            for workspace_report in workspace_reports
            if workspace_report.direct_shared_proof_consumer
            for code in workspace_report.sunset_enforcement_codes
            if code != "shared-proof-direct-consumer-not-registry-only"
        }
    )
    legacy_workspace_blockers = sorted(
        {
            f"{workspace_report.workspace_classification}-workspaces-remain"
            for workspace_report in workspace_reports
            if workspace_report.direct_shared_proof_consumer
            and workspace_report.workspace_classification
            in {
                ProofArtifactWorkspaceMode.MANIFEST_ONLY.value,
                ProofArtifactWorkspaceMode.MIXED.value,
                ProofArtifactWorkspaceMode.MISSING.value,
            }
        }
    )
    alias_active_workspace_blockers = sorted(
        {
            f"{ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE.value}-workspaces-remain"
            for workspace_report in workspace_reports
            if workspace_report.direct_shared_proof_consumer
            and workspace_report.normalization_classification
            == ProofArtifactNormalizationMode.REGISTRY_ONLY_ALIAS_ACTIVE.value
        }
    )

    if not workspace_reports and not discovery_issues:
        sunset_readiness_status = "no-workspaces-discovered"
        sunset_blockers: list[str] = []
    elif discovery_issues:
        sunset_readiness_status = "blocked-by-discovery-errors"
        sunset_blockers = [issue.issue_code for issue in discovery_issues]
    elif normal_path_debt_present or direct_consumer_normal_path_debt:
        sunset_readiness_status = "blocked-by-normal-path-debt"
        sunset_blockers = direct_consumer_normal_path_debt or ["legacy-manifest-normal-path-debt-present"]
    elif legacy_workspace_blockers:
        sunset_readiness_status = "blocked-by-legacy-workspaces"
        sunset_blockers = legacy_workspace_blockers
    elif alias_active_workspace_blockers:
        sunset_readiness_status = "blocked-by-alias-active-workspaces"
        sunset_blockers = alias_active_workspace_blockers
    else:
        sunset_readiness_status = "fleet-registry-only-steady-state"
        sunset_blockers = []

    fleet_report_path = _fleet_report_path(resolved_scan_root, report_path)
    report = ProofArtifactFleetReport(
        scan_root=Path(scan_root).resolve().as_posix(),
        report_path=_display_path(fleet_report_path, resolved_scan_root),
        apply_requested=apply,
        dry_run=not apply,
        selected_classifications=selected_classifications,
        discovered_workspace_count=len(workspace_reports),
        workspace_counts_by_classification=classification_counts,
        workspace_counts_by_normalization_classification=normalization_classification_counts,
        migration_required_count=migration_required_count,
        migration_applied_count=migration_applied_count,
        direct_shared_proof_consumer_count=direct_shared_proof_consumer_count,
        fingerprint_continuity_counts=continuity_counts,
        compat_debt_summary=compat_debt_summary,
        repo_surface_status_counts=repo_surface_status_counts,
        steady_state_enforcement_passed=sunset_readiness_status == "fleet-registry-only-steady-state",
        sunset_readiness_status=sunset_readiness_status,
        sunset_blockers=sunset_blockers,
        discovery_errors=discovery_issues,
        legacy_surface_audit=audit_rows,
        workspaces=workspace_reports,
    )
    save_state_file(report, fleet_report_path)
    return report


def rehearse_proof_artifact_sunset(
    scan_root: str | Path,
    *,
    report_path: str | Path | None = None,
) -> ProofArtifactVNextBlockerReport:
    fleet_report = inspect_or_normalize_proof_artifact_fleet(scan_root, apply=False)
    resolved_scan_root, _explicit_configs = _resolved_scan_root(scan_root)

    blockers: list[ProofArtifactVNextBlocker] = []
    workspace_reports: list[ProofArtifactVNextWorkspaceReport] = []
    blocker_counts_by_category: dict[str, int] = {}

    for blocker in _discovery_issue_blockers(list(fleet_report.discovery_errors)):
        blockers.append(blocker)

    for workspace_report in fleet_report.workspaces:
        workspace_blockers: list[ProofArtifactVNextBlocker] = []
        if workspace_report.direct_shared_proof_consumer:
            classification_blocker = _workspace_classification_blocker(workspace_report)
            if classification_blocker is not None:
                workspace_blockers.append(classification_blocker)
            workspace_blockers.extend(_workspace_alias_blockers(workspace_report))
            workspace_blockers.extend(_workspace_enforcement_blockers(workspace_report))
        blockers.extend(workspace_blockers)

        blocker_categories = [blocker.blocker_category for blocker in workspace_blockers]
        blocker_codes = [blocker.blocker_code for blocker in workspace_blockers]
        suggested_actions = [blocker.suggested_action for blocker in workspace_blockers]
        workspace_reports.append(
            ProofArtifactVNextWorkspaceReport(
                workspace_root=workspace_report.workspace_root,
                config_path=workspace_report.config_path,
                workflow_option=workspace_report.workflow_option,
                direct_shared_proof_consumer=workspace_report.direct_shared_proof_consumer,
                workspace_classification=workspace_report.workspace_classification,
                normalization_classification=workspace_report.normalization_classification,
                removal_ready=not workspace_blockers,
                doctor_report_path=workspace_report.doctor_report_path,
                proof_unit_registry_path=workspace_report.proof_unit_registry_path,
                proof_module_manifest_path=workspace_report.proof_module_manifest_path,
                content_plan_path=workspace_report.content_plan_path,
                pipeline_state_path=workspace_report.pipeline_state_path,
                fingerprint_continuity_status=workspace_report.fingerprint_continuity_status,
                fingerprint_continuity_risk=_fingerprint_continuity_risk(
                    normalization_classification=workspace_report.normalization_classification,
                    workspace_classification=workspace_report.workspace_classification,
                    fingerprint_continuity_status=workspace_report.fingerprint_continuity_status,
                ),
                blocker_categories=blocker_categories,
                blocker_codes=blocker_codes,
                suggested_actions=suggested_actions,
            )
        )

    repo_surface_blockers = _repo_surface_blockers()
    blockers.extend(repo_surface_blockers)

    for blocker in blockers:
        category_key = blocker.blocker_category.value
        blocker_counts_by_category[category_key] = blocker_counts_by_category.get(category_key, 0) + 1

    blocker_categories_present = [
        category
        for category in ProofArtifactSunsetBlockerCategory
        if blocker_counts_by_category.get(category.value, 0) > 0
    ]
    exit_criteria = _build_exit_criteria(
        discovered_workspace_count=fleet_report.discovered_workspace_count,
        discovery_errors=list(fleet_report.discovery_errors),
        blocker_counts_by_category=blocker_counts_by_category,
    )
    removal_ready = all(criterion.status == ProofArtifactRemovalExitCriterionStatus.PASS for criterion in exit_criteria)
    rehearsal_status = _rehearsal_status(
        discovered_workspace_count=fleet_report.discovered_workspace_count,
        discovery_errors=list(fleet_report.discovery_errors),
        blocker_counts_by_category=blocker_counts_by_category,
    )
    vnext_report_path = _vnext_blocker_report_path(resolved_scan_root, report_path)
    report = ProofArtifactVNextBlockerReport(
        scan_root=Path(scan_root).resolve().as_posix(),
        report_path=_display_path(vnext_report_path, resolved_scan_root),
        source_fleet_report_path=fleet_report.report_path,
        rehearsal_mode="registry-only-vnext-removal",
        strict_mode_simulated=True,
        dry_run=True,
        discovered_workspace_count=fleet_report.discovered_workspace_count,
        direct_shared_proof_consumer_count=fleet_report.direct_shared_proof_consumer_count,
        removal_ready_workspace_count=sum(1 for workspace in workspace_reports if workspace.removal_ready),
        workspace_counts_by_classification=dict(sorted(fleet_report.workspace_counts_by_classification.items())),
        workspace_counts_by_normalization_classification=dict(
            sorted(fleet_report.workspace_counts_by_normalization_classification.items())
        ),
        fingerprint_continuity_counts=dict(sorted(fleet_report.fingerprint_continuity_counts.items())),
        blocker_counts_by_category=dict(sorted(blocker_counts_by_category.items())),
        compat_debt_summary=dict(sorted(fleet_report.compat_debt_summary.items())),
        repo_surface_status_counts=dict(sorted(fleet_report.repo_surface_status_counts.items())),
        blocker_categories_present=blocker_categories_present,
        removal_ready=removal_ready,
        rehearsal_status=rehearsal_status,
        removal_exit_criteria_passed=removal_ready,
        exit_criteria=exit_criteria,
        discovery_errors=list(fleet_report.discovery_errors),
        blockers=blockers,
        workspaces=workspace_reports,
        recommended_next_step=_recommended_rehearsal_next_step(rehearsal_status),
        warnings=[],
    )
    save_state_file(report, vnext_report_path)
    return report
