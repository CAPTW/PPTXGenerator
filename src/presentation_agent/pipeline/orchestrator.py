"""Orchestration rules for the evidence-first stage-gated harness."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from pydantic import ValidationError

from ..non_pptx_modules.state_schemas import (
    RenderValidationVerdict,
    load_state_file,
    proof_unit_registry_from_proof_module_manifest,
)
from ..non_pptx_modules.shared_proof_registry import (
    LEGACY_PROOF_MODULE_MANIFEST_FINGERPRINT_KEY,
    PROOF_ARTIFACT_COMPAT_WARNING_SCOPE,
    PROOF_ARTIFACT_CONTRACT_VERSION,
    PROOF_ARTIFACT_SUNSET_PHASE,
    PROOF_UNIT_REGISTRY_FINGERPRINT_KEY,
    canonical_shared_proof_fingerprint_key,
    proof_artifact_contract_regression_codes,
    shared_proof_consumer_policy,
)
from .invalidation import (
    InputAssetSnapshot,
    determine_invalidation_stage,
    determine_invalidation_stage_from_fingerprints,
    extract_intake_assets,
    fingerprint_path,
    fingerprint_assets,
)
from .gate_policy import DEFAULT_GATE_APPROVAL_POLICY, GateApprovalPolicy, GateStateSnapshot
from .render_validation import validate_local_pptx
from .state_store import ArtifactEnvelope, FingerprintRecord, PipelineHistoryEntry, PipelineRunStatus, PipelineState, PipelineStateStore
from .stages import PIPELINE_STAGE_ORDER, PipelineStage, coerce_stage, stage_index
from .tool_acl import assert_tool_allowed


class StageTransitionError(RuntimeError):
    """Raised when an artifact is recorded out of order."""


class ArtifactValidationError(ValueError):
    """Raised when a stage artifact violates harness rules."""


@dataclass(slots=True)
class StageRunResult:
    stage: PipelineStage
    skipped: bool
    status: str
    detail: str
    artifact_path: str | None = None


@dataclass(slots=True)
class PipelineRunResult:
    success: bool
    blocked: bool
    final_stage: PipelineStage
    final_status: PipelineRunStatus
    final_pptx_path: str | None
    stage_results: list[StageRunResult]


class PipelineOrchestrator:
    """Validates stage transitions, gate outcomes, and render completion requirements."""

    def __init__(
        self,
        store: PipelineStateStore,
        *,
        workspace_root: str | Path | None = None,
        gate_policy: GateApprovalPolicy | None = None,
    ):
        self.store = store
        self.workspace_root = Path(workspace_root) if workspace_root is not None else store.root.parent
        self.gate_policy = gate_policy or DEFAULT_GATE_APPROVAL_POLICY

    def load_state(self) -> PipelineState:
        return self.store.load_pipeline_state()

    def gate_state(self) -> GateStateSnapshot:
        return GateStateSnapshot.from_state(self.load_state())

    def ensure_tool_allowed(self, stage: PipelineStage | str, tool_name: str) -> None:
        assert_tool_allowed(stage, tool_name)

    def refresh_fingerprints(self, records: list[FingerprintRecord | dict[str, object]]) -> PipelineState:
        normalized = self._normalize_fingerprints(
            [record if isinstance(record, FingerprintRecord) else FingerprintRecord.model_validate(record) for record in records]
        )
        state = self.store.load_pipeline_state()
        previous_records = self._normalize_fingerprints(state.fingerprints)
        invalidation_stage = determine_invalidation_stage_from_fingerprints(previous_records, normalized)
        joined_fingerprint = self._combined_fingerprint(normalized)
        if invalidation_stage is None:
            state.fingerprints = normalized
            state.last_input_fingerprint = joined_fingerprint
            self.store.save_pipeline_state(state)
            return state
        updated_state = self.store.invalidate_from(
            invalidation_stage,
            state=state,
            last_input_fingerprint=joined_fingerprint,
        )
        updated_state.fingerprints = normalized
        self.store.save_pipeline_state(updated_state)
        return updated_state

    def refresh_inputs(self, assets: list[InputAssetSnapshot | dict[str, object]]) -> PipelineState:
        normalized_assets = [
            asset if isinstance(asset, InputAssetSnapshot) else InputAssetSnapshot.model_validate(asset) for asset in assets
        ]
        current_fingerprint = fingerprint_assets(normalized_assets)
        state = self.store.load_pipeline_state()
        previous_assets = extract_intake_assets(self.store.load_artifact(PipelineStage.INGEST))
        invalidation_stage = determine_invalidation_stage(previous_assets, normalized_assets)

        if state.last_input_fingerprint == current_fingerprint and invalidation_stage is None:
            return state
        if invalidation_stage is None:
            state.last_input_fingerprint = current_fingerprint
            self.store.save_pipeline_state(state)
            return state
        return self.store.invalidate_from(
            invalidation_stage,
            state=state,
            last_input_fingerprint=current_fingerprint,
        )

    def run(
        self,
        executors: dict[PipelineStage, object],
        *,
        from_stage: PipelineStage | str | None = None,
        to_stage: PipelineStage | str | None = None,
        force_stages: set[PipelineStage | str] | None = None,
        fingerprint_records: list[FingerprintRecord | dict[str, object]] | None = None,
    ) -> PipelineRunResult:
        normalized_force = {coerce_stage(stage) for stage in (force_stages or set())}
        if fingerprint_records is not None:
            self.refresh_fingerprints(fingerprint_records)
        if normalized_force:
            earliest_force = min(normalized_force, key=stage_index)
            current_state = self.store.load_pipeline_state()
            self.store.invalidate_from(
                earliest_force,
                state=current_state,
                last_input_fingerprint=current_state.last_input_fingerprint,
            )
        state = self.store.load_pipeline_state()
        start_stage = coerce_stage(from_stage) if from_stage is not None else PIPELINE_STAGE_ORDER[0]
        end_stage = coerce_stage(to_stage) if to_stage is not None else PIPELINE_STAGE_ORDER[-1]
        if stage_index(end_stage) < stage_index(start_stage):
            raise ValueError("to_stage must not come before from_stage")

        stage_results: list[StageRunResult] = []
        for stage in PIPELINE_STAGE_ORDER[stage_index(start_stage) : stage_index(end_stage) + 1]:
            gate_state = self.gate_state()
            state = self.store.load_pipeline_state()
            if gate_state.run_status == PipelineRunStatus.COMPLETE:
                artifact = self.store.load_artifact(stage)
                if artifact is not None and self.gate_policy.is_success(stage, artifact.status):
                    stage_results.append(
                        StageRunResult(
                            stage=stage,
                            skipped=True,
                            status=artifact.status,
                            detail=f"{stage.value} already approved.",
                            artifact_path=str(self.store.artifact_path(stage)),
                        )
                    )
                    continue
                break
            if stage_index(stage) < stage_index(gate_state.current_stage):
                artifact = self.store.load_artifact(stage)
                if artifact is not None and self.gate_policy.is_success(stage, artifact.status):
                    stage_results.append(
                        StageRunResult(
                            stage=stage,
                            skipped=True,
                            status=artifact.status,
                            detail=f"{stage.value} already approved.",
                            artifact_path=str(self.store.artifact_path(stage)),
                        )
                    )
                    continue
            if stage != gate_state.current_stage:
                if gate_state.run_status in {PipelineRunStatus.BLOCKED, PipelineRunStatus.COMPLETE}:
                    break
                raise StageTransitionError(f"{stage.value} is not currently runnable; expected {gate_state.current_stage.value}")
            executor = executors[stage]
            result = executor.execute(current_stage=gate_state.current_stage, force=stage in normalized_force)
            updated_state = self.record_artifact(result.artifact)
            stage_results.append(
                StageRunResult(
                    stage=stage,
                    skipped=False,
                    status=result.artifact.status,
                    detail=result.detail,
                    artifact_path=str(self.store.artifact_path(stage)),
                )
            )
            if updated_state.status == PipelineRunStatus.BLOCKED:
                break
        final_state = self.store.load_pipeline_state()
        final_pptx_path = self.final_pptx_path() if final_state.status == PipelineRunStatus.COMPLETE else None
        return PipelineRunResult(
            success=final_state.status == PipelineRunStatus.COMPLETE,
            blocked=final_state.status == PipelineRunStatus.BLOCKED,
            final_stage=final_state.current_stage,
            final_status=final_state.status,
            final_pptx_path=final_pptx_path,
            stage_results=stage_results,
        )

    def resume(
        self,
        executors: dict[PipelineStage, object],
        *,
        to_stage: PipelineStage | str | None = None,
        force_stages: set[PipelineStage | str] | None = None,
        fingerprint_records: list[FingerprintRecord | dict[str, object]] | None = None,
    ) -> PipelineRunResult:
        return self.run(
            executors,
            from_stage=None,
            to_stage=to_stage,
            force_stages=force_stages,
            fingerprint_records=fingerprint_records,
        )

    def final_pptx_path(self) -> str | None:
        artifact = self.store.load_artifact(PipelineStage.RENDER_LOCAL_PPTX)
        if artifact is None or not self.gate_policy.is_success(PipelineStage.RENDER_LOCAL_PPTX, artifact.status):
            return None
        extras = artifact.model_extra or {}
        pptx_path = extras.get("pptx_path")
        if not isinstance(pptx_path, str) or not pptx_path:
            return None
        return str(self._resolve_pptx_path(pptx_path))

    def record_artifact(self, artifact: ArtifactEnvelope | dict[str, object]) -> PipelineState:
        envelope = artifact if isinstance(artifact, ArtifactEnvelope) else ArtifactEnvelope.model_validate(artifact)
        state = self.store.load_pipeline_state()
        if envelope.stage != state.current_stage:
            raise StageTransitionError(
                f"{envelope.stage.value} is not the current legal stage; expected {state.current_stage.value}"
            )

        self._validate_prerequisites(envelope)
        self._validate_stage_specific_rules(envelope)
        artifact_path = self.store.save_artifact(envelope)

        state.history.append(
            PipelineHistoryEntry(
                stage=envelope.stage,
                status=envelope.status,
                artifact=str(artifact_path),
                created_at=envelope.created_at,
            )
        )

        if envelope.stage == PipelineStage.INGEST:
            intake_assets = extract_intake_assets(envelope)
            if intake_assets:
                state.last_input_fingerprint = fingerprint_assets(intake_assets)
            state.invalidated_from_stage = None
        stage_fingerprints = self._extract_stage_fingerprints(envelope)
        if stage_fingerprints:
            state.fingerprints = self._merge_fingerprints(state.fingerprints, stage_fingerprints)
            state.last_input_fingerprint = self._combined_fingerprint(state.fingerprints)

        if self.gate_policy.is_success(envelope.stage, envelope.status):
            transition = self.gate_policy.approved_transition(envelope.stage, envelope.status)
            state.approved_artifacts[envelope.stage.value] = str(artifact_path)
            state.invalidated_from_stage = None
            state.current_stage = transition.resulting_stage
            state.status = transition.run_status
        else:
            transition = self.gate_policy.blocked_transition(
                envelope.stage,
                rollback_stage=self._rollback_target(envelope),
                status=envelope.status,
            )
            state.current_stage = transition.resulting_stage
            state.status = transition.run_status

        self.store.save_pipeline_state(state)
        return state

    def _validate_prerequisites(self, artifact: ArtifactEnvelope) -> None:
        if artifact.stage == PipelineStage.INGEST:
            return
        if artifact.stage == PipelineStage.DESIGN_REFERENCE_CHECK:
            self._require_success(PipelineStage.INGEST)
            return
        if artifact.stage == PipelineStage.MASTER_TEMPLATE:
            self._require_success(PipelineStage.DESIGN_REFERENCE_CHECK)
            return
        if artifact.stage == PipelineStage.CONTENT_PLAN:
            self._require_success(PipelineStage.MASTER_TEMPLATE)
            return
        if artifact.stage == PipelineStage.GENERATE:
            self._require_success(PipelineStage.MASTER_TEMPLATE)
            self._require_success(PipelineStage.CONTENT_PLAN)
            return
        if artifact.stage == PipelineStage.QA:
            self._require_success(PipelineStage.GENERATE)
            return
        if artifact.stage == PipelineStage.RENDER_LOCAL_PPTX:
            self._require_success(PipelineStage.QA)
            return
        raise StageTransitionError(f"unknown stage {artifact.stage.value}")

    def _validate_stage_specific_rules(self, artifact: ArtifactEnvelope) -> None:
        if artifact.stage == PipelineStage.DESIGN_REFERENCE_CHECK:
            self._validate_design_reference_check(artifact)
        elif artifact.stage == PipelineStage.MASTER_TEMPLATE:
            self._validate_master_template(artifact)
        elif artifact.stage == PipelineStage.CONTENT_PLAN:
            self._validate_content_plan(artifact)
        elif artifact.stage == PipelineStage.RENDER_LOCAL_PPTX:
            self._validate_render_report(artifact)

    def _validate_design_reference_check(self, artifact: ArtifactEnvelope) -> None:
        if not self.gate_policy.is_success(artifact.stage, artifact.status):
            return
        intake_artifact = self._require_success(PipelineStage.INGEST)
        intake_assets = extract_intake_assets(intake_artifact)
        user_design_reference_ids = {
            asset.asset_id for asset in intake_assets if "design_reference" in set(asset.roles)
        }
        if not user_design_reference_ids:
            return
        extras = artifact.model_extra or {}
        references = extras.get("references")
        if not isinstance(references, list) or not references:
            raise ArtifactValidationError(
                "DESIGN_REFERENCE_CHECK must cite user-provided design_reference assets before approval."
            )
        referenced_ids = {
            str(reference.get("asset_id")).strip()
            for reference in references
            if isinstance(reference, dict) and reference.get("asset_id")
        }
        if not referenced_ids:
            raise ArtifactValidationError(
                "DESIGN_REFERENCE_CHECK approval requires at least one user-provided design reference asset_id."
            )
        unknown_ids = referenced_ids - user_design_reference_ids
        if unknown_ids:
            raise ArtifactValidationError(
                "Generic or unknown design references cannot replace user-provided design references: "
                + ", ".join(sorted(unknown_ids))
            )

    def _validate_render_report(self, artifact: ArtifactEnvelope) -> None:
        if not self.gate_policy.is_success(artifact.stage, artifact.status):
            return
        extras = artifact.model_extra or {}
        pptx_path_value = extras.get("pptx_path")
        if not isinstance(pptx_path_value, str) or not pptx_path_value.strip():
            raise ArtifactValidationError("RENDER_LOCAL_PPTX success requires a non-empty pptx_path.")
        candidate_path = Path(pptx_path_value)
        parsed = urlparse(pptx_path_value)
        if parsed.scheme and not candidate_path.drive and parsed.scheme not in {"", "file"}:
            raise ArtifactValidationError("RENDER_LOCAL_PPTX success requires a local file path, not a remote URL.")
        pptx_path = candidate_path
        if not pptx_path.is_absolute():
            pptx_path = (self.workspace_root / pptx_path).resolve()
        if pptx_path.suffix.lower() != ".pptx":
            raise ArtifactValidationError("RENDER_LOCAL_PPTX success requires a .pptx output path.")
        try:
            validation = validate_local_pptx(pptx_path)
        except FileNotFoundError as exc:
            raise ArtifactValidationError(f"RENDER_LOCAL_PPTX success requires an existing local file: {pptx_path}") from exc
        except ValueError as exc:
            raise ArtifactValidationError(str(exc)) from exc
        render_rule_summary = extras.get("render_rule_summary")
        verdict = None
        if render_rule_summary is not None:
            try:
                verdict = RenderValidationVerdict.model_validate(render_rule_summary)
            except ValidationError as exc:
                raise ArtifactValidationError("RENDER_LOCAL_PPTX render_rule_summary is not schema-valid.") from exc
            if not verdict.validation_passed:
                raise ArtifactValidationError("RENDER_LOCAL_PPTX success requires render_rule_summary.validation_passed=true.")
            compile_eligibility = extras.get("compile_eligibility")
            if compile_eligibility is not None:
                eligibility_value = str(getattr(compile_eligibility, "value", compile_eligibility)).strip()
                if eligibility_value != verdict.compile_eligibility.value:
                    raise ArtifactValidationError(
                        "RENDER_LOCAL_PPTX compile_eligibility must match render_rule_summary.compile_eligibility."
                    )
            compatibility_warning_codes = extras.get("compatibility_warning_codes")
            if compatibility_warning_codes is not None:
                if not isinstance(compatibility_warning_codes, list):
                    raise ArtifactValidationError(
                        "RENDER_LOCAL_PPTX compatibility_warning_codes must be a list when render_rule_summary is present."
                    )
                normalized_codes = list(dict.fromkeys(str(code).strip() for code in compatibility_warning_codes if str(code).strip()))
                if normalized_codes != list(verdict.compatibility_warning_codes):
                    raise ArtifactValidationError(
                        "RENDER_LOCAL_PPTX compatibility_warning_codes must match render_rule_summary.compatibility_warning_codes."
                    )
        render_validation = extras.get("render_validation")
        if render_validation is None:
            if verdict is None:
                raise ArtifactValidationError(
                    "RENDER_LOCAL_PPTX success requires render_rule_summary or render_validation metadata."
                )
            return
        if not isinstance(render_validation, dict):
            raise ArtifactValidationError("RENDER_LOCAL_PPTX render_validation must be a dict when provided.")
        if render_validation.get("slide_count") != validation["slide_count"]:
            raise ArtifactValidationError("RENDER_LOCAL_PPTX render_validation.slide_count must match the validated PPTX slide count.")
        if render_validation.get("checksum") != validation["checksum"]:
            raise ArtifactValidationError("RENDER_LOCAL_PPTX render_validation.checksum must match the validated PPTX checksum.")
        if render_validation.get("zip_readable") is not True or render_validation.get("presentation_xml_present") is not True:
            raise ArtifactValidationError("RENDER_LOCAL_PPTX success requires a structurally valid PPTX archive.")

    def _validate_content_plan(self, artifact: ArtifactEnvelope) -> None:
        extras = artifact.model_extra or {}
        workflow_option = extras.get("workflow_option")
        workflow_option_provenance = extras.get("workflow_option_provenance")
        plan_conformance = extras.get("plan_conformance")
        if not isinstance(workflow_option_provenance, dict):
            raise ArtifactValidationError("CONTENT_PLAN artifacts must record workflow_option_provenance.")
        selected_option_id = workflow_option_provenance.get("selected_option_id")
        if not isinstance(selected_option_id, str) or not selected_option_id.strip():
            raise ArtifactValidationError("CONTENT_PLAN workflow_option_provenance requires selected_option_id.")
        policy_id = workflow_option_provenance.get("policy_id")
        if not isinstance(policy_id, str) or not policy_id.strip():
            raise ArtifactValidationError("CONTENT_PLAN workflow_option_provenance requires policy_id.")
        resolution_code = workflow_option_provenance.get("resolution_code")
        if not isinstance(resolution_code, str) or not resolution_code.strip():
            raise ArtifactValidationError("CONTENT_PLAN workflow_option_provenance requires resolution_code.")
        contractable_option_ids = workflow_option_provenance.get("contractable_option_ids")
        if not isinstance(contractable_option_ids, list):
            raise ArtifactValidationError("CONTENT_PLAN workflow_option_provenance requires contractable_option_ids.")
        if workflow_option is not None and workflow_option != selected_option_id:
            raise ArtifactValidationError("CONTENT_PLAN workflow_option must match workflow_option_provenance.selected_option_id.")
        if not isinstance(plan_conformance, dict):
            raise ArtifactValidationError("CONTENT_PLAN artifacts must record plan_conformance.")
        if plan_conformance.get("selected_option_id") != selected_option_id:
            raise ArtifactValidationError("CONTENT_PLAN plan_conformance.selected_option_id must match the selected workflow option.")
        conformance_policy_id = plan_conformance.get("policy_id")
        if not isinstance(conformance_policy_id, str) or not conformance_policy_id.strip():
            raise ArtifactValidationError("CONTENT_PLAN plan_conformance requires policy_id.")
        if conformance_policy_id != policy_id:
            raise ArtifactValidationError("CONTENT_PLAN plan_conformance.policy_id must match workflow_option_provenance.policy_id.")
        required_sections = plan_conformance.get("required_sections")
        required_main_story_roles = plan_conformance.get("required_main_story_roles")
        failure_codes = plan_conformance.get("failure_codes")
        proof_unit_registry_path = extras.get("proof_unit_registry_path")
        proof_unit_registry_summary = extras.get("proof_unit_registry_summary")
        if not isinstance(required_sections, list):
            raise ArtifactValidationError("CONTENT_PLAN plan_conformance requires required_sections.")
        if not isinstance(required_main_story_roles, list):
            raise ArtifactValidationError("CONTENT_PLAN plan_conformance requires required_main_story_roles.")
        if not isinstance(failure_codes, list):
            raise ArtifactValidationError("CONTENT_PLAN plan_conformance requires failure_codes.")
        proof_module_manifest_path = extras.get("proof_module_manifest_path")
        proof_module_manifest_summary = extras.get("proof_module_manifest_summary")
        if self.gate_policy.is_success(artifact.stage, artifact.status):
            if str(plan_conformance.get("status")).lower() != "pass":
                raise ArtifactValidationError("Approved CONTENT_PLAN artifacts require a passing plan_conformance status.")
            accepted_checks = plan_conformance.get("accepted_checks")
            if not isinstance(accepted_checks, list) or not accepted_checks:
                raise ArtifactValidationError("Approved CONTENT_PLAN artifacts require non-empty accepted_checks.")
            if failure_codes:
                raise ArtifactValidationError("Approved CONTENT_PLAN artifacts cannot include failure_codes.")
            shared_proof_policy = shared_proof_consumer_policy(selected_option_id)
            if shared_proof_policy is not None:
                from ..non_pptx_modules.state_schemas import load_state_file

                if isinstance(proof_unit_registry_path, str) and proof_unit_registry_path.strip():
                    resolved_registry_path = Path(proof_unit_registry_path)
                    if not resolved_registry_path.is_absolute():
                        resolved_registry_path = (self.workspace_root / resolved_registry_path).resolve()
                    if not resolved_registry_path.is_file():
                        raise ArtifactValidationError(
                            f"CONTENT_PLAN proof_unit_registry_path does not exist: {resolved_registry_path}"
                        )
                    proof_unit_registry = load_state_file(resolved_registry_path)
                    if getattr(proof_unit_registry, "schema_name", None) != "proof_unit_registry":
                        raise ArtifactValidationError(
                            "CONTENT_PLAN proof_unit_registry_path must point to a proof_unit_registry state artifact."
                        )
                    if getattr(proof_unit_registry, "workflow_option", None) != selected_option_id:
                        raise ArtifactValidationError(
                            "CONTENT_PLAN proof_unit_registry workflow_option must match the selected workflow option."
                        )
                    if not isinstance(proof_unit_registry_summary, dict):
                        raise ArtifactValidationError(
                            "Approved evidence-backed-core CONTENT_PLAN artifacts require proof_unit_registry_summary when proof_unit_registry_path is present."
                        )
                    if proof_unit_registry_summary.get("unit_count") != getattr(proof_unit_registry, "unit_count", None):
                        raise ArtifactValidationError(
                            "CONTENT_PLAN proof_unit_registry_summary.unit_count must match the persisted proof-unit registry."
                        )
                else:
                    raise ArtifactValidationError(
                        f"Approved `{selected_option_id}` CONTENT_PLAN artifacts require proof_unit_registry_path."
                    )
                if isinstance(proof_module_manifest_path, str) and proof_module_manifest_path.strip():
                    raise ArtifactValidationError(
                        f"Approved `{selected_option_id}` CONTENT_PLAN artifacts must keep proof_module_manifest_path out of the normal registry-first persistence path."
                    )
                proof_artifact_contract = extras.get("proof_artifact_contract")
                contract_failure_codes = proof_artifact_contract_regression_codes(
                    selected_option_id,
                    proof_artifact_contract=proof_artifact_contract if isinstance(proof_artifact_contract, dict) else None,
                    proof_unit_registry_path=proof_unit_registry_path if isinstance(proof_unit_registry_path, str) else None,
                    proof_module_manifest_path=proof_module_manifest_path if isinstance(proof_module_manifest_path, str) else None,
                )
                if contract_failure_codes:
                    raise ArtifactValidationError(
                        "CONTENT_PLAN proof_artifact_contract violates shared-proof registry-only steady-state rules: "
                        + ", ".join(contract_failure_codes)
                    )
        else:
            if str(plan_conformance.get("status")).lower() != "fail":
                raise ArtifactValidationError("Blocked CONTENT_PLAN artifacts require a failing plan_conformance status.")
            failure_reasons = plan_conformance.get("failure_reasons")
            if not isinstance(failure_reasons, list) or not failure_reasons:
                raise ArtifactValidationError("Blocked CONTENT_PLAN artifacts require failure_reasons.")
            if not failure_codes:
                raise ArtifactValidationError("Blocked CONTENT_PLAN artifacts require failure_codes.")

    def _require_success(self, stage: PipelineStage) -> ArtifactEnvelope:
        artifact = self.store.load_artifact(stage)
        if artifact is None:
            raise StageTransitionError(f"{stage.value} has no artifact yet.")
        if not self.gate_policy.is_success(stage, artifact.status):
            raise StageTransitionError(f"{stage.value} is not approved; current status is {artifact.status}.")
        return artifact

    def _rollback_target(self, artifact: ArtifactEnvelope) -> PipelineStage:
        extras = artifact.model_extra or {}
        rollback_stage = extras.get("next_stage")
        if rollback_stage is None:
            return artifact.stage
        candidate = coerce_stage(rollback_stage)
        if stage_index(candidate) > stage_index(artifact.stage):
            raise ArtifactValidationError(
                f"blocking stage {artifact.stage.value} cannot redirect forward to {candidate.value}"
            )
        return candidate

    def _validate_master_template(self, artifact: ArtifactEnvelope) -> None:
        if not self.gate_policy.is_success(artifact.stage, artifact.status):
            return
        extras = artifact.model_extra or {}
        required_keys = {
            "template_bundle_path",
            "style_tokens",
            "source_reference_ids",
            "approval_basis",
            "created_from_stage_attempt",
        }
        missing = sorted(key for key in required_keys if key not in extras)
        if missing:
            raise ArtifactValidationError("MASTER_TEMPLATE approval requires: " + ", ".join(missing))
        bundle_path = extras.get("template_bundle_path")
        if not isinstance(bundle_path, str) or not bundle_path.strip():
            raise ArtifactValidationError("MASTER_TEMPLATE requires a non-empty template_bundle_path.")
        resolved_bundle_path = Path(bundle_path)
        if not resolved_bundle_path.is_absolute():
            resolved_bundle_path = (self.workspace_root / resolved_bundle_path).resolve()
        if not resolved_bundle_path.is_file():
            raise ArtifactValidationError(f"MASTER_TEMPLATE template_bundle_path does not exist: {resolved_bundle_path}")
        if not isinstance(extras.get("style_tokens"), list) or not extras.get("style_tokens"):
            raise ArtifactValidationError("MASTER_TEMPLATE requires non-empty style_tokens.")
        if not isinstance(extras.get("source_reference_ids"), list):
            raise ArtifactValidationError("MASTER_TEMPLATE requires source_reference_ids.")
        if not isinstance(extras.get("approval_basis"), list) or not extras.get("approval_basis"):
            raise ArtifactValidationError("MASTER_TEMPLATE requires non-empty approval_basis.")
        attempt = extras.get("created_from_stage_attempt")
        if not isinstance(attempt, int) or attempt < 1:
            raise ArtifactValidationError("MASTER_TEMPLATE created_from_stage_attempt must be a positive integer.")

    def _extract_stage_fingerprints(self, artifact: ArtifactEnvelope) -> list[FingerprintRecord]:
        extras = artifact.model_extra or {}
        raw = extras.get("fingerprints")
        if not isinstance(raw, list):
            return []
        return [record if isinstance(record, FingerprintRecord) else FingerprintRecord.model_validate(record) for record in raw]

    def _merge_fingerprints(self, previous: list[FingerprintRecord], current: list[FingerprintRecord]) -> list[FingerprintRecord]:
        merged = {record.key: record for record in self._normalize_fingerprints(previous)}
        for record in self._normalize_fingerprints(current):
            merged[record.key] = record
        return [merged[key] for key in sorted(merged)]

    def _combined_fingerprint(self, records: list[FingerprintRecord]) -> str:
        normalized = self._normalize_fingerprints(records)
        joined = "|".join(
            f"{record.key}:{record.digest}:{record.invalidates_from_stage.value}"
            for record in sorted(normalized, key=lambda item: item.key)
        )
        return hashlib.sha256(joined.encode("utf-8")).hexdigest() if joined else ""

    def _normalize_fingerprints(self, records: list[FingerprintRecord]) -> list[FingerprintRecord]:
        normalized: dict[str, FingerprintRecord] = {}
        for record in records:
            normalized_record = self._normalize_proof_fingerprint_record(record)
            normalized[normalized_record.key] = normalized_record
        return [normalized[key] for key in sorted(normalized)]

    def _normalize_proof_fingerprint_record(self, record: FingerprintRecord) -> FingerprintRecord:
        canonical_key = canonical_shared_proof_fingerprint_key(record.key)
        if canonical_key != PROOF_UNIT_REGISTRY_FINGERPRINT_KEY:
            return record
        proof_record = self._canonical_proof_fingerprint_record(record.invalidates_from_stage)
        if proof_record is None:
            return record.model_copy(update={"key": canonical_key})
        return proof_record

    def _canonical_proof_fingerprint_record(self, invalidates_from_stage: PipelineStage) -> FingerprintRecord | None:
        proof_unit_registry_path = self.workspace_root / "state" / "proof-unit-registry.json"
        proof_module_manifest_path = self.workspace_root / "state" / "proof-module-manifest.json"
        if proof_unit_registry_path.is_file():
            proof_unit_registry = load_state_file(proof_unit_registry_path)
            return FingerprintRecord(
                key=PROOF_UNIT_REGISTRY_FINGERPRINT_KEY,
                digest=self._semantic_proof_digest(proof_unit_registry.to_payload()),
                invalidates_from_stage=invalidates_from_stage,
                sources=[self._display_workspace_path(proof_unit_registry_path)],
            )
        if proof_module_manifest_path.is_file():
            proof_module_manifest = load_state_file(proof_module_manifest_path)
            proof_unit_registry = proof_unit_registry_from_proof_module_manifest(proof_module_manifest)
            return FingerprintRecord(
                key=PROOF_UNIT_REGISTRY_FINGERPRINT_KEY,
                digest=self._semantic_proof_digest(proof_unit_registry.to_payload()),
                invalidates_from_stage=invalidates_from_stage,
                sources=[self._display_workspace_path(proof_module_manifest_path)],
            )
        return None

    def _semantic_proof_digest(self, payload: dict[str, object]) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()

    def _display_workspace_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.workspace_root)).replace("\\", "/")
        except ValueError:
            return str(path)

    def _resolve_pptx_path(self, pptx_path_value: str) -> Path:
        pptx_path = Path(pptx_path_value)
        if not pptx_path.is_absolute():
            pptx_path = (self.workspace_root / pptx_path).resolve()
        return pptx_path
