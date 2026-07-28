"""Phase 16 ship-readiness decision and cycle reset control."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ..pptx_compiler import BuildManifest, SlideBuildLinkage, load_pptx_compile_file
from ..compat.legacy_non_pptx import (
    ApprovalPacketSet,
    ApplyDecisionStatus,
    ApprovedApplyReport,
    AssetManifest,
    AuthoringDeltas,
    BatchManifest,
    ClosureReasonStatus,
    ClosureReport,
    CompileQAHealthSummary,
    ContextLock,
    ContractModel,
    CycleResetPlan,
    CycleStartStage,
    DEFAULT_STATE_FILENAMES,
    DeckConstitution,
    DesignSystem,
    FindingStatus,
    HandoffPacket,
    LayoutLibrary,
    PendingApprovalSummary,
    QAGovernance,
    QAReport,
    ReleaseCandidate,
    ReleaseReadinessPosture,
    ReleaseReadinessSummary,
    RemainingBacklog,
    RemainingBacklogItem,
    RemainingBacklogSnapshot,
    RemediationExecutionReport,
    RemediationPlan,
    ShipReadinessDecision,
    ShipReadinessReport,
    SlideLedger,
    StateCapsule,
    StateFilePointer,
    UpstreamFixPlan,
    Blueprint,
    VizManifest,
    load_state_file,
    save_state_file,
)


class ShipReadinessOutputs(ContractModel):
    ship_readiness_report: ShipReadinessReport
    cycle_reset_plan: CycleResetPlan
    state_capsule: StateCapsule
    handoff_packet: HandoffPacket | None = None
    release_candidate: ReleaseCandidate | None = None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _upsert_pointer(pointers: list[StateFilePointer], *, schema_name: str, path: str) -> list[StateFilePointer]:
    updated: list[StateFilePointer] = []
    replaced = False
    for pointer in pointers:
        if pointer.schema_name == schema_name:
            updated.append(StateFilePointer(schema_name=schema_name, path=path, required=True))
            replaced = True
        else:
            updated.append(pointer)
    if not replaced:
        updated.append(StateFilePointer(schema_name=schema_name, path=path, required=True))
    return updated


def _remove_pointer(pointers: list[StateFilePointer], *, schema_name: str) -> list[StateFilePointer]:
    return [pointer for pointer in pointers if pointer.schema_name != schema_name]


def _canonical_state_root(
    state_capsule: StateCapsule,
    closure_report: ClosureReport,
    remaining_backlog: RemainingBacklog,
    artifact_root: Path,
    state_output_dir: Path,
) -> str:
    for candidate in (
        state_capsule.canonical_state_root,
        closure_report.canonical_state_root,
        remaining_backlog.canonical_state_root,
    ):
        if candidate:
            return candidate
    return _display_path(state_output_dir, artifact_root)


def _remaining_snapshot(remaining_backlog: RemainingBacklog) -> RemainingBacklogSnapshot:
    return RemainingBacklogSnapshot.model_validate(remaining_backlog.summary.model_dump())


def _status_value(value: object) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", value)


def _resolved_qa_policy_summary(qa_report: QAReport):
    summary = qa_report.verdict_summary
    if summary is None:
        return None
    if summary.qa_status != qa_report.qa_status:
        return None
    return summary


def _compile_qa_health(qa_report: QAReport, build_manifest: BuildManifest, slide_build_linkage: SlideBuildLinkage) -> CompileQAHealthSummary:
    qa_policy_summary = _resolved_qa_policy_summary(qa_report)
    open_findings = [finding for finding in qa_report.findings if finding.status == FindingStatus.OPEN]
    blocking_findings = [finding for finding in open_findings if finding.blocking]
    incomplete_slides = [slide for slide in slide_build_linkage.slides if _status_value(slide.compile_status) != "complete"]
    missing_dependency_slides = [slide for slide in slide_build_linkage.slides if slide.missing_dependencies]
    compatibility_warning_codes = list(qa_policy_summary.compatibility_warning_codes) if qa_policy_summary is not None else []
    if build_manifest.warnings and "build-warning-string-surface" not in compatibility_warning_codes:
        compatibility_warning_codes.append("build-warning-string-surface")
    return CompileQAHealthSummary(
        qa_status=qa_policy_summary.qa_status if qa_policy_summary is not None else qa_report.qa_status,
        compile_eligibility=qa_policy_summary.compile_eligibility if qa_policy_summary is not None else None,
        qa_warning_reason_codes=list(qa_policy_summary.warning_reason_codes) if qa_policy_summary is not None else [],
        qa_blocking_reason_codes=list(qa_policy_summary.blocking_reason_codes) if qa_policy_summary is not None else [],
        compatibility_warning_codes=compatibility_warning_codes,
        qa_open_finding_count=len(open_findings),
        qa_blocking_finding_count=len(blocking_findings),
        qa_open_finding_ids=[finding.finding_id for finding in open_findings],
        qa_blocking_finding_ids=[finding.finding_id for finding in blocking_findings],
        build_warning_count=len(build_manifest.warnings),
        build_warnings=list(build_manifest.warnings),
        compile_incomplete_slide_count=len(incomplete_slides),
        compile_incomplete_slide_numbers=[slide.slide_number for slide in incomplete_slides],
        missing_dependency_count=len(missing_dependency_slides),
        missing_dependency_slide_numbers=[slide.slide_number for slide in missing_dependency_slides],
    )


def _build_warning_signal_count(health: CompileQAHealthSummary) -> int:
    if "build-warning-string-surface" in health.compatibility_warning_codes:
        if health.build_warning_count > 0:
            return health.build_warning_count
        if health.build_warnings:
            return len(health.build_warnings)
        return 1
    return health.build_warning_count


def _pending_approval_summary(remaining_backlog: RemainingBacklog) -> PendingApprovalSummary:
    pending_items = [item for item in remaining_backlog.items if item.status == ClosureReasonStatus.PENDING_APPROVAL]
    return PendingApprovalSummary(
        pending_packet_count=len(remaining_backlog.pending_packet_ids),
        pending_fix_count=len([item for item in pending_items if item.fix_id is not None]),
        pending_packet_ids=list(remaining_backlog.pending_packet_ids),
        pending_fix_ids=[item.fix_id for item in pending_items if item.fix_id is not None],
    )


def _warning_count(closure_report: ClosureReport, remaining_backlog: RemainingBacklog, health: CompileQAHealthSummary) -> int:
    non_blocking_open_findings = max(health.qa_open_finding_count - health.qa_blocking_finding_count, 0)
    build_warning_signal_count = _build_warning_signal_count(health)
    return len(closure_report.warnings) + len(remaining_backlog.warnings) + build_warning_signal_count + non_blocking_open_findings


def _release_candidate_id(deck_title: str) -> str:
    return f"release-candidate-{deck_title.lower().replace(' ', '-')}"


def _governance_blocker_reasons(qa_report: QAReport, qa_governance: QAGovernance) -> list[str]:
    summary = qa_governance.summary
    reasons: list[str] = []
    if qa_governance.source_report_id != qa_report.report_id:
        reasons.append(
            f"qa-governance.json points to qa report `{qa_governance.source_report_id}` instead of the active `{qa_report.report_id}`."
        )
    if qa_report.governance_report_id and qa_report.governance_report_id != qa_governance.governance_id:
        reasons.append(
            f"qa-report.json points to governance report `{qa_report.governance_report_id}` instead of `{qa_governance.governance_id}`."
        )
    if summary.blocking_findings_still_open > 0:
        reasons.append(f"{summary.blocking_findings_still_open} blocking governance-linked finding(s) remain open.")
    if summary.expired_waiver_count > 0:
        reasons.append(f"{summary.expired_waiver_count} waiver(s) are expired and do not clear release readiness.")
    if summary.orphan_waiver_count > 0:
        reasons.append(f"{summary.orphan_waiver_count} waiver record(s) are orphaned from current or prior findings.")
    if summary.orphan_remediation_count > 0:
        reasons.append(f"{summary.orphan_remediation_count} remediation record(s) do not match any finding.")
    if summary.remediation_mismatch_count > 0:
        reasons.append(
            f"{summary.remediation_mismatch_count} remediation record(s) claim fixed or verified status while QA still finds the issue."
        )
    return _dedupe(reasons)


def _operator_exception_reason(qa_governance: QAGovernance) -> str | None:
    if not qa_governance.summary.depends_on_operator_exceptions:
        return None
    return "Release posture depends on active operator-approved waivers or accepted-risk records."


def derive_release_readiness_summary(
    *,
    qa_report: QAReport,
    qa_governance: QAGovernance,
    build_manifest: BuildManifest,
    ship_gate_ready: bool,
    ship_gate_reasons: list[str],
    related_stage: str,
    generated_by: str,
) -> ReleaseReadinessSummary:
    summary = qa_governance.summary
    notes: list[str] = []
    if qa_governance.source_report_id != qa_report.report_id:
        notes.append("Governance source_report_id does not match the qa-report used for this readiness decision.")
    if qa_report.governance_report_id and qa_report.governance_report_id != qa_governance.governance_id:
        notes.append("qa-report governance_report_id does not match the persisted qa-governance artifact.")

    posture = ReleaseReadinessPosture.REPO_BACKED_CLEAR
    rationale = "No unresolved blocking QA or governance issues remain."
    blocker_reasons = _governance_blocker_reasons(qa_report, qa_governance)
    if not ship_gate_ready:
        posture = ReleaseReadinessPosture.UNRESOLVED_BLOCKING_ISSUE
        rationale = ship_gate_reasons[0] if ship_gate_reasons else "Ship-readiness assessment still has unresolved release blockers."
    elif blocker_reasons:
        posture = ReleaseReadinessPosture.UNRESOLVED_BLOCKING_ISSUE
        rationale = blocker_reasons[0]
        notes.extend(blocker_reasons[1:])
    elif summary.depends_on_operator_exceptions:
        posture = ReleaseReadinessPosture.OPERATOR_ENFORCED_EXCEPTION
        rationale = "The deck may ship, but release posture depends on active operator-approved exceptions."

    return ReleaseReadinessSummary(
        related_stage=related_stage,
        qa_report_id=qa_report.report_id,
        governance_report_id=qa_governance.governance_id,
        build_artifact_references=_dedupe(["build-manifest.json", build_manifest.linkage_path, build_manifest.pptx_path]),
        generated_by=generated_by,
        release_posture=posture,
        total_findings=qa_report.summary.finding_count or len(qa_report.findings),
        blocking_findings_open_count=summary.blocking_findings_still_open,
        waived_findings_count=summary.waived_findings,
        accepted_risk_count=summary.accepted_risk_findings,
        remediated_findings_count=summary.remediated_findings,
        expired_waiver_count=summary.expired_waiver_count,
        orphan_waiver_count=summary.orphan_waiver_count,
        orphan_remediation_count=summary.orphan_remediation_count,
        remediation_mismatch_count=summary.remediation_mismatch_count,
        operator_exception_dependency=summary.depends_on_operator_exceptions,
        ship_ready=ship_gate_ready and posture != ReleaseReadinessPosture.UNRESOLVED_BLOCKING_ISSUE,
        rationale_summary=rationale,
        notes=_dedupe(notes),
    )


def _carry_forward_items(remaining_backlog: RemainingBacklog) -> list[RemainingBacklogItem]:
    actionable = {
        ClosureReasonStatus.PENDING_APPROVAL,
        ClosureReasonStatus.DEFERRED,
        ClosureReasonStatus.BLOCKED_MANUAL,
        ClosureReasonStatus.FAILED_REVIEW_NEEDED,
    }
    return [item for item in remaining_backlog.items if item.status in actionable]


def _determine_decision(
    *,
    closure_report: ClosureReport,
    remaining_backlog: RemainingBacklog,
    remediation_plan: RemediationPlan,
    remediation_execution_report: RemediationExecutionReport,
    health: CompileQAHealthSummary,
    qa_report: QAReport,
    qa_governance: QAGovernance,
) -> tuple[ShipReadinessDecision, bool, CycleStartStage | None, list[str]]:
    reasons: list[str] = []
    if remaining_backlog.summary.blocked_manual_items > 0:
        reasons.append(
            f"{remaining_backlog.summary.blocked_manual_items} manual-blocked backlog item(s) remain: {', '.join(remaining_backlog.blocked_issue_ids)}."
        )
        reasons.extend(remaining_backlog.recommended_next_actions)
        return ShipReadinessDecision.BLOCKED_MANUAL, False, CycleStartStage.AUTHOR_UPSTREAM_FIXES, _dedupe(reasons)

    compile_blocker = health.compile_incomplete_slide_count > 0 or health.missing_dependency_count > 0
    if compile_blocker:
        reasons.append("Compile output is incomplete for one or more slides in slide-build-linkage.json.")
    if health.qa_blocking_finding_count > 0:
        reasons.append(
            f"{health.qa_blocking_finding_count} blocking QA finding(s) remain: {', '.join(health.qa_blocking_finding_ids)}."
        )
    if remaining_backlog.summary.pending_approval_items > 0:
        reasons.append(
            f"{remaining_backlog.summary.pending_approval_items} pending approval item(s) remain: {', '.join(remaining_backlog.pending_packet_ids)}."
        )
    if remaining_backlog.summary.failed_review_items > 0:
        reasons.append(f"{remaining_backlog.summary.failed_review_items} approved item(s) still need deterministic review.")
    if remediation_plan.ship_blocked:
        reasons.append("remediation-plan.json still marks the deck as ship_blocked.")
    if remediation_execution_report.ship_blocked_after_execution:
        reasons.append("remediation-execution-report.json still marks the deck as ship_blocked_after_execution.")
    if closure_report.still_open_packet_count > 0 and remaining_backlog.summary.pending_approval_items == 0:
        reasons.append(f"{closure_report.still_open_packet_count} approval packet(s) remain open after closure.")
    reasons.extend(_governance_blocker_reasons(qa_report, qa_governance))

    if reasons:
        next_stage = CycleStartStage.APPLY_APPROVED_FIXES if remaining_backlog.summary.pending_approval_items > 0 else CycleStartStage.AUTHOR_UPSTREAM_FIXES
        return ShipReadinessDecision.NEEDS_NEXT_BOUNDED_CYCLE, False, next_stage, _dedupe(reasons)

    build_warning_signal_count = _build_warning_signal_count(health)
    non_blocking_signals = (
        remaining_backlog.summary.remaining_actionable_items > 0
        or health.qa_open_finding_count > 0
        or build_warning_signal_count > 0
    )
    operator_exception_reason = _operator_exception_reason(qa_governance)
    if operator_exception_reason is not None:
        non_blocking_signals = True
    if non_blocking_signals:
        reasons = []
        if remaining_backlog.summary.deferred_items > 0:
            reasons.append(f"{remaining_backlog.summary.deferred_items} deferred backlog item(s) remain and are carry-forward only.")
        if health.qa_open_finding_count > 0:
            reasons.append(f"{health.qa_open_finding_count} non-blocking QA finding(s) remain open.")
        if build_warning_signal_count > 0:
            reasons.append(f"Build manifest still carries {build_warning_signal_count} warning(s).")
        if operator_exception_reason is not None:
            reasons.append(operator_exception_reason)
        return ShipReadinessDecision.READY_TO_SHIP_WITH_NON_BLOCKING_BACKLOG, True, CycleStartStage.SHIP_DECK, _dedupe(reasons)

    return ShipReadinessDecision.READY_TO_SHIP, True, CycleStartStage.SHIP_DECK, [
        "No blocking QA findings, compile blockers, pending approvals, or actionable backlog remain."
    ]


def _next_action_for_decision(
    decision: ShipReadinessDecision,
    *,
    remaining_backlog: RemainingBacklog,
    next_stage: CycleStartStage | None,
) -> str:
    if decision == ShipReadinessDecision.READY_TO_SHIP:
        return "Ship the canonical deck using release-candidate.json as the release reference."
    if decision == ShipReadinessDecision.READY_TO_SHIP_WITH_NON_BLOCKING_BACKLOG:
        return "The deck may ship now; keep remaining non-blocking backlog for a later bounded cycle."
    if remaining_backlog.recommended_next_actions:
        return remaining_backlog.recommended_next_actions[0]
    if next_stage is not None:
        return f"Continue at `{next_stage.value}` for the next bounded cycle."
    return "Review the remaining backlog before the next bounded cycle."


def _locked_artifacts(release_candidate_emitted: bool) -> list[str]:
    locked = [
        "blueprint.json",
        "design-system.json",
        "deck-constitution.json",
        "layout-library.json",
        "slide-ledger.json",
        "approval-packet.json",
        "authoring-deltas.json",
        "upstream-fix-plan.json",
        "approved-apply-report.json",
        "closure-report.json",
        "remaining-backlog.json",
        "build-manifest.json",
        "qa-report.json",
        "qa-governance.json",
        "state-capsule.json",
        "handoff-packet.json",
    ]
    if release_candidate_emitted:
        locked.append("release-candidate.json")
    return locked


def _first_batch_id(items: list[RemainingBacklogItem], fallback: str | None) -> str | None:
    for item in items:
        if item.affected_batch_ids:
            return item.affected_batch_ids[0]
    return fallback


def _build_release_candidate(
    *,
    candidate_id: str,
    report: ShipReadinessReport,
    release_readiness: ReleaseReadinessSummary,
    remaining_snapshot: RemainingBacklogSnapshot,
    build_manifest: BuildManifest,
    canonical_state_root: str,
) -> ReleaseCandidate | None:
    if report.decision not in {
        ShipReadinessDecision.READY_TO_SHIP,
        ShipReadinessDecision.READY_TO_SHIP_WITH_NON_BLOCKING_BACKLOG,
    } or not release_readiness.ship_ready:
        return None
    return ReleaseCandidate(
        candidate_id=candidate_id,
        deck_title=report.deck_title,
        source_ship_readiness_report_id=report.report_id,
        source_qa_report_id=release_readiness.qa_report_id,
        source_governance_report_id=release_readiness.governance_report_id,
        decision=report.decision,
        canonical_deck_path=build_manifest.pptx_path,
        canonical_build_manifest_path=DEFAULT_STATE_FILENAMES["build_manifest"] if "build_manifest" in DEFAULT_STATE_FILENAMES else "build-manifest.json",
        canonical_qa_report_path=DEFAULT_STATE_FILENAMES["qa_report"],
        canonical_state_capsule_path=DEFAULT_STATE_FILENAMES["state_capsule"],
        release_summary=report.next_recommended_action,
        release_readiness=release_readiness,
        remaining_backlog_summary=remaining_snapshot,
        non_blocking_notes=list(report.reasons if report.decision == ShipReadinessDecision.READY_TO_SHIP_WITH_NON_BLOCKING_BACKLOG else []),
        warnings=list(report.warnings),
        canonical_state_root=canonical_state_root,
    )


def _update_state_capsule(
    state_capsule: StateCapsule,
    *,
    decision: ShipReadinessDecision,
    may_ship_now: bool,
    next_cycle_required: bool,
    next_stage: CycleStartStage | None,
    remaining_snapshot: RemainingBacklogSnapshot,
    carry_forward_items: list[RemainingBacklogItem],
    report: ShipReadinessReport,
    release_candidate: ReleaseCandidate | None,
    pointer_root: str,
    next_batch_id: str | None,
) -> StateCapsule:
    file_pointers = list(state_capsule.file_pointers)
    for schema_name in ("ship_readiness_report", "cycle_reset_plan"):
        file_pointers = _upsert_pointer(
            file_pointers,
            schema_name=schema_name,
            path=f"{pointer_root}/{DEFAULT_STATE_FILENAMES[schema_name]}",
        )
    if release_candidate is not None:
        file_pointers = _upsert_pointer(
            file_pointers,
            schema_name="release_candidate",
            path=f"{pointer_root}/{DEFAULT_STATE_FILENAMES['release_candidate']}",
        )
    else:
        file_pointers = _remove_pointer(file_pointers, schema_name="release_candidate")

    open_issue_summaries = _dedupe([item.summary for item in carry_forward_items] + list(report.reasons))
    pending_actions = [report.next_recommended_action]
    if next_cycle_required:
        pending_actions.extend(item.recommended_next_action for item in carry_forward_items)

    return state_capsule.model_copy(
        update={
            "open_issues": _dedupe(open_issue_summaries),
            "pending_actions": _dedupe(pending_actions),
            "remediation_backlog_count": remaining_snapshot.remaining_actionable_items,
            "pending_approval_packet_ids": list(report.pending_approval_summary.pending_packet_ids),
            "pending_upstream_fix_ids": list(report.unresolved_fix_ids),
            "cycle_outcome": decision,
            "deck_shippable": may_ship_now,
            "next_cycle_required": next_cycle_required,
            "next_recommended_stage": next_stage,
            "next_recommended_batch_id": next_batch_id,
            "remaining_backlog_snapshot": remaining_snapshot,
            "file_pointers": file_pointers,
            "updated_at": datetime.now(UTC),
        }
    )


def _update_handoff_packet(
    handoff_packet: HandoffPacket,
    *,
    decision: ShipReadinessDecision,
    may_ship_now: bool,
    next_cycle_required: bool,
    next_stage: CycleStartStage | None,
    remaining_snapshot: RemainingBacklogSnapshot,
    carry_forward_items: list[RemainingBacklogItem],
    report: ShipReadinessReport,
    release_candidate: ReleaseCandidate | None,
    pointer_root: str,
    next_batch_id: str | None,
) -> HandoffPacket:
    file_pointers = list(handoff_packet.file_pointers)
    for schema_name in ("ship_readiness_report", "cycle_reset_plan"):
        file_pointers = _upsert_pointer(
            file_pointers,
            schema_name=schema_name,
            path=f"{pointer_root}/{DEFAULT_STATE_FILENAMES[schema_name]}",
        )
    if release_candidate is not None:
        file_pointers = _upsert_pointer(
            file_pointers,
            schema_name="release_candidate",
            path=f"{pointer_root}/{DEFAULT_STATE_FILENAMES['release_candidate']}",
        )
    else:
        file_pointers = _remove_pointer(file_pointers, schema_name="release_candidate")

    produced_artifacts = _dedupe(
        list(handoff_packet.produced_artifacts)
        + [
            DEFAULT_STATE_FILENAMES["ship_readiness_report"],
            DEFAULT_STATE_FILENAMES["cycle_reset_plan"],
        ]
        + ([DEFAULT_STATE_FILENAMES["release_candidate"]] if release_candidate is not None else [])
    )
    reviewed_artifacts = _dedupe(
        list(handoff_packet.reviewed_artifacts)
        + [
            DEFAULT_STATE_FILENAMES["closure_report"],
            DEFAULT_STATE_FILENAMES["remaining_backlog"],
            DEFAULT_STATE_FILENAMES["qa_governance"],
            DEFAULT_STATE_FILENAMES["ship_readiness_report"],
        ]
    )
    verification_items_open = [item.item_id for item in carry_forward_items]
    instructions = [report.next_recommended_action]
    if next_cycle_required and next_stage is not None:
        instructions.append(f"Start the next bounded cycle at `{next_stage.value}` after the required human step completes.")

    return handoff_packet.model_copy(
        update={
            "file_pointers": file_pointers,
            "produced_artifacts": produced_artifacts,
            "reviewed_artifacts": reviewed_artifacts,
            "open_issues": _dedupe([item.summary for item in carry_forward_items] + list(report.reasons)),
            "verification_items_open": verification_items_open,
            "pending_approval_packet_ids": list(report.pending_approval_summary.pending_packet_ids),
            "pending_upstream_fix_ids": list(report.unresolved_fix_ids),
            "handoff_instructions": _dedupe(instructions),
            "cycle_outcome": decision,
            "deck_shippable": may_ship_now,
            "next_cycle_required": next_cycle_required,
            "next_recommended_stage": next_stage,
            "next_recommended_batch_id": next_batch_id,
            "remaining_backlog_snapshot": remaining_snapshot,
            "generated_at": datetime.now(UTC),
        }
    )


def assess_ship_readiness(
    *,
    closure_report: ClosureReport,
    remaining_backlog: RemainingBacklog,
    approval_packet: ApprovalPacketSet,
    authoring_deltas: AuthoringDeltas,
    upstream_fix_plan: UpstreamFixPlan,
    approved_apply_report: ApprovedApplyReport,
    remediation_plan: RemediationPlan,
    remediation_execution_report: RemediationExecutionReport,
    batch_manifest: BatchManifest,
    context_lock: ContextLock,
    handoff_packet: HandoffPacket,
    state_capsule: StateCapsule,
    slide_ledger: SlideLedger,
    slide_build_linkage: SlideBuildLinkage,
    qa_report: QAReport,
    qa_governance: QAGovernance,
    build_manifest: BuildManifest,
    blueprint: Blueprint,
    design_system: DesignSystem,
    deck_constitution: DeckConstitution,
    layout_library: LayoutLibrary,
    asset_manifest: AssetManifest,
    viz_manifest: VizManifest,
    artifact_root: Path,
    state_output_dir: Path,
) -> ShipReadinessOutputs:
    del approval_packet
    del authoring_deltas
    del upstream_fix_plan
    del approved_apply_report
    del batch_manifest
    del context_lock
    del slide_ledger
    del blueprint
    del design_system
    del deck_constitution
    del layout_library
    del asset_manifest
    del viz_manifest

    canonical_state_root = _canonical_state_root(state_capsule, closure_report, remaining_backlog, artifact_root, state_output_dir)
    remaining_snapshot = _remaining_snapshot(remaining_backlog)
    health = _compile_qa_health(qa_report, build_manifest, slide_build_linkage)
    pending_summary = _pending_approval_summary(remaining_backlog)
    candidate_id = _release_candidate_id(closure_report.deck_title)
    decision, may_ship_now, next_stage, reasons = _determine_decision(
        closure_report=closure_report,
        remaining_backlog=remaining_backlog,
        remediation_plan=remediation_plan,
        remediation_execution_report=remediation_execution_report,
        health=health,
        qa_report=qa_report,
        qa_governance=qa_governance,
    )
    release_readiness = derive_release_readiness_summary(
        qa_report=qa_report,
        qa_governance=qa_governance,
        build_manifest=build_manifest,
        ship_gate_ready=may_ship_now,
        ship_gate_reasons=reasons,
        related_stage="assess-ship-readiness",
        generated_by="ship-readiness.assess_ship_readiness",
    )
    carry_forward = _carry_forward_items(remaining_backlog)
    next_cycle_required = decision in {
        ShipReadinessDecision.NEEDS_NEXT_BOUNDED_CYCLE,
        ShipReadinessDecision.BLOCKED_MANUAL,
    }
    next_action = _next_action_for_decision(decision, remaining_backlog=remaining_backlog, next_stage=next_stage)
    unresolved_fix_ids = _dedupe([item.fix_id for item in carry_forward if item.fix_id is not None])
    unresolved_finding_ids = _dedupe(
        [finding_id for item in carry_forward for finding_id in item.finding_ids] + list(health.qa_blocking_finding_ids)
    )

    report = ShipReadinessReport(
        report_id=f"ship-readiness-{closure_report.report_id}",
        deck_title=closure_report.deck_title,
        source_closure_report_id=closure_report.report_id,
        source_remaining_backlog_id=remaining_backlog.backlog_id,
        source_approved_apply_report_id=closure_report.source_approved_apply_report_id,
        source_qa_report_id=qa_report.report_id,
        source_governance_report_id=qa_governance.governance_id,
        release_candidate_id=candidate_id,
        decision=decision,
        may_ship_now=release_readiness.ship_ready,
        blocker_count=(
            health.qa_blocking_finding_count
            + health.compile_incomplete_slide_count
            + health.missing_dependency_count
            + remaining_snapshot.blocked_manual_items
            + qa_governance.summary.expired_waiver_count
            + qa_governance.summary.orphan_waiver_count
            + qa_governance.summary.orphan_remediation_count
            + qa_governance.summary.remediation_mismatch_count
        ),
        warning_count=_warning_count(closure_report, remaining_backlog, health),
        reasons=reasons,
        pending_approval_summary=pending_summary,
        remaining_backlog_summary=remaining_snapshot,
        compile_qa_health=health,
        blocked_issue_ids=list(remaining_backlog.blocked_issue_ids),
        unresolved_fix_ids=unresolved_fix_ids,
        unresolved_finding_ids=unresolved_finding_ids,
        canonical_artifact_references=_locked_artifacts(release_candidate_emitted=False),
        release_readiness=release_readiness,
        next_recommended_action=next_action,
        warnings=_dedupe(list(closure_report.warnings) + list(remaining_backlog.warnings) + list(health.build_warnings)),
        notes=[
            *closure_report.safe_partial_rerun_notes,
            *release_readiness.notes,
            "Phase 16 did not apply new fixes or rerun production workers; it only assessed the current canonical state.",
        ],
        canonical_state_root=canonical_state_root,
    )
    release_candidate = _build_release_candidate(
        candidate_id=candidate_id,
        report=report,
        release_readiness=release_readiness,
        remaining_snapshot=remaining_snapshot,
        build_manifest=build_manifest,
        canonical_state_root=canonical_state_root,
    )
    report = report.model_copy(
        update={
            "canonical_artifact_references": _locked_artifacts(release_candidate_emitted=release_candidate is not None)
        }
    )

    carry_forward_packet_ids = _dedupe([item.packet_id for item in carry_forward if item.packet_id is not None])
    carry_forward_fix_ids = _dedupe([item.fix_id for item in carry_forward if item.fix_id is not None])
    carry_forward_blocked_issue_ids = _dedupe([item.issue_id for item in carry_forward if item.issue_id is not None])
    carry_forward_finding_ids = _dedupe([finding_id for item in carry_forward for finding_id in item.finding_ids])
    next_batch_id = _first_batch_id(carry_forward, state_capsule.next_recommended_batch_id or handoff_packet.next_recommended_batch_id) if next_cycle_required else None
    cycle_reset_plan = CycleResetPlan(
        plan_id=f"cycle-reset-{closure_report.report_id}",
        deck_title=closure_report.deck_title,
        source_closure_report_id=closure_report.report_id,
        source_remaining_backlog_id=remaining_backlog.backlog_id,
        source_ship_readiness_report_id=report.report_id,
        decision=decision,
        current_cycle_closed=True,
        may_ship_now=may_ship_now,
        next_cycle_required=next_cycle_required,
        carry_forward_items=carry_forward,
        carry_forward_packet_ids=carry_forward_packet_ids,
        carry_forward_fix_ids=carry_forward_fix_ids,
        carry_forward_blocked_issue_ids=carry_forward_blocked_issue_ids,
        carry_forward_finding_ids=carry_forward_finding_ids,
        locked_artifacts=_locked_artifacts(release_candidate_emitted=release_candidate is not None),
        next_recommended_starting_stage=next_stage,
        next_recommended_batch_id=next_batch_id,
        reset_rules=[
            "Keep previously applied and closed approval packets closed; carry forward only unresolved backlog items.",
            "Retain the current canonical blueprint, design system, layout library, build manifest, and QA report until an approved next cycle changes them.",
        ],
        retain_rules=[
            "Use closure-report.json and remaining-backlog.json as the authoritative closure lineage for the completed cycle.",
            "Keep state-capsule.json and handoff-packet.json synchronized with the current ship decision.",
        ],
        archive_notes=[
            "Applied approval packets remain archived through closure-report.json.",
            "Do not reopen closed packets unless a new approval lineage is authored.",
        ],
        notes=[
            "No new deltas were applied in Phase 16.",
            *closure_report.safe_partial_rerun_notes,
        ],
        canonical_state_root=canonical_state_root,
    )

    updated_state_capsule = _update_state_capsule(
        state_capsule,
        decision=decision,
        may_ship_now=may_ship_now,
        next_cycle_required=next_cycle_required,
        next_stage=next_stage,
        remaining_snapshot=remaining_snapshot,
        carry_forward_items=carry_forward,
        report=report,
        release_candidate=release_candidate,
        pointer_root=canonical_state_root,
        next_batch_id=next_batch_id,
    )
    updated_handoff_packet = _update_handoff_packet(
        handoff_packet,
        decision=decision,
        may_ship_now=may_ship_now,
        next_cycle_required=next_cycle_required,
        next_stage=next_stage,
        remaining_snapshot=remaining_snapshot,
        carry_forward_items=carry_forward,
        report=report,
        release_candidate=release_candidate,
        pointer_root=canonical_state_root,
        next_batch_id=next_batch_id,
    )

    return ShipReadinessOutputs(
        ship_readiness_report=report,
        cycle_reset_plan=cycle_reset_plan,
        state_capsule=updated_state_capsule,
        handoff_packet=updated_handoff_packet,
        release_candidate=release_candidate,
    )


def assess_ship_readiness_from_files(
    closure_report_path: str | Path,
    remaining_backlog_path: str | Path,
    approval_packet_path: str | Path,
    authoring_deltas_path: str | Path,
    upstream_fix_plan_path: str | Path,
    approved_apply_report_path: str | Path,
    remediation_plan_path: str | Path,
    remediation_execution_report_path: str | Path,
    batch_manifest_path: str | Path,
    context_lock_path: str | Path,
    handoff_packet_path: str | Path,
    state_capsule_path: str | Path,
    slide_ledger_path: str | Path,
    slide_build_linkage_path: str | Path,
    qa_report_path: str | Path,
    qa_governance_path: str | Path,
    build_manifest_path: str | Path,
    blueprint_path: str | Path,
    design_system_path: str | Path,
    deck_constitution_path: str | Path,
    layout_library_path: str | Path,
    asset_manifest_path: str | Path,
    viz_manifest_path: str | Path,
    *,
    artifact_root: str | Path | None = None,
    state_output_dir: str | Path | None = None,
) -> ShipReadinessOutputs:
    closure_report = load_state_file(closure_report_path)
    remaining_backlog = load_state_file(remaining_backlog_path)
    approval_packet = load_state_file(approval_packet_path)
    authoring_deltas = load_state_file(authoring_deltas_path)
    upstream_fix_plan = load_state_file(upstream_fix_plan_path)
    approved_apply_report = load_state_file(approved_apply_report_path)
    remediation_plan = load_state_file(remediation_plan_path)
    remediation_execution_report = load_state_file(remediation_execution_report_path)
    batch_manifest = load_state_file(batch_manifest_path)
    context_lock = load_state_file(context_lock_path)
    handoff_packet = load_state_file(handoff_packet_path)
    state_capsule = load_state_file(state_capsule_path)
    slide_ledger = load_state_file(slide_ledger_path)
    qa_report = load_state_file(qa_report_path)
    qa_governance = load_state_file(qa_governance_path)
    blueprint = load_state_file(blueprint_path)
    design_system = load_state_file(design_system_path)
    deck_constitution = load_state_file(deck_constitution_path)
    layout_library = load_state_file(layout_library_path)
    asset_manifest = load_state_file(asset_manifest_path)
    viz_manifest = load_state_file(viz_manifest_path)
    build_manifest = load_pptx_compile_file(build_manifest_path)
    slide_build_linkage = load_pptx_compile_file(slide_build_linkage_path)

    expected = [
        (closure_report, "closure_report"),
        (remaining_backlog, "remaining_backlog"),
        (approval_packet, "approval_packet"),
        (authoring_deltas, "authoring_deltas"),
        (upstream_fix_plan, "upstream_fix_plan"),
        (approved_apply_report, "approved_apply_report"),
        (remediation_plan, "remediation_plan"),
        (remediation_execution_report, "remediation_execution_report"),
        (batch_manifest, "batch_manifest"),
        (context_lock, "context_lock"),
        (handoff_packet, "handoff_packet"),
        (state_capsule, "state_capsule"),
        (slide_ledger, "slide_ledger"),
        (qa_report, "qa_report"),
        (qa_governance, "qa_governance"),
        (blueprint, "blueprint"),
        (design_system, "design_system"),
        (deck_constitution, "deck_constitution"),
        (layout_library, "layout_library"),
        (asset_manifest, "asset_manifest"),
        (viz_manifest, "viz_manifest"),
    ]
    for model, schema_name in expected:
        if model.schema_name != schema_name:
            raise TypeError(f"expected {schema_name}, found {model.schema_name}")
    if build_manifest.schema_name != "build_manifest":
        raise TypeError(f"expected build_manifest, found {build_manifest.schema_name}")
    if slide_build_linkage.schema_name != "slide_build_linkage":
        raise TypeError(f"expected slide_build_linkage, found {slide_build_linkage.schema_name}")

    resolved_state_output_dir = Path(state_output_dir) if state_output_dir is not None else Path(state_capsule_path).resolve().parent
    resolved_artifact_root = Path(artifact_root) if artifact_root is not None else resolved_state_output_dir
    return assess_ship_readiness(
        closure_report=closure_report,
        remaining_backlog=remaining_backlog,
        approval_packet=approval_packet,
        authoring_deltas=authoring_deltas,
        upstream_fix_plan=upstream_fix_plan,
        approved_apply_report=approved_apply_report,
        remediation_plan=remediation_plan,
        remediation_execution_report=remediation_execution_report,
        batch_manifest=batch_manifest,
        context_lock=context_lock,
        handoff_packet=handoff_packet,
        state_capsule=state_capsule,
        slide_ledger=slide_ledger,
        slide_build_linkage=slide_build_linkage,
        qa_report=qa_report,
        qa_governance=qa_governance,
        build_manifest=build_manifest,
        blueprint=blueprint,
        design_system=design_system,
        deck_constitution=deck_constitution,
        layout_library=layout_library,
        asset_manifest=asset_manifest,
        viz_manifest=viz_manifest,
        artifact_root=resolved_artifact_root,
        state_output_dir=resolved_state_output_dir,
    )


def write_ship_readiness_outputs(outputs: ShipReadinessOutputs, output_dir: str | Path) -> dict[str, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    written = {
        "ship_readiness_report": save_state_file(
            outputs.ship_readiness_report,
            root / DEFAULT_STATE_FILENAMES["ship_readiness_report"],
        ),
        "cycle_reset_plan": save_state_file(
            outputs.cycle_reset_plan,
            root / DEFAULT_STATE_FILENAMES["cycle_reset_plan"],
        ),
        "state_capsule": save_state_file(outputs.state_capsule, root / DEFAULT_STATE_FILENAMES["state_capsule"]),
    }
    if outputs.handoff_packet is not None:
        written["handoff_packet"] = save_state_file(
            outputs.handoff_packet,
            root / DEFAULT_STATE_FILENAMES["handoff_packet"],
        )
    if outputs.release_candidate is not None:
        written["release_candidate"] = save_state_file(
            outputs.release_candidate,
            root / DEFAULT_STATE_FILENAMES["release_candidate"],
        )
    return written


