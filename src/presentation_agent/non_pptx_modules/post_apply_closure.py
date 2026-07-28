"""Phase 15 post-apply closure, remaining backlog, and control-state synchronization."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ..compat.legacy_non_pptx import WorkflowGate
from ..pptx_compiler import BuildManifest, SlideBuildLinkage, load_pptx_compile_file
from ..compat.legacy_non_pptx import (
    ApprovalDecisionStatus,
    ApprovalPacket,
    ApprovalPacketSet,
    ApplyDecisionStatus,
    ApprovedApplyReport,
    AssetManifest,
    AssetRequests,
    AuthoringDeltaRecord,
    AuthoringDeltas,
    BacklogItemType,
    BatchManifest,
    BlockedManualUpstreamIssue,
    Blueprint,
    ClosureReasonStatus,
    ClosureReport,
    ClosureReportSummary,
    ContextLock,
    ContractModel,
    DEFAULT_STATE_FILENAMES,
    DeckConstitution,
    DesignSystem,
    HandoffPacket,
    LayoutLibrary,
    QAReport,
    QASeverity,
    RemainingBacklog,
    RemainingBacklogItem,
    RemainingBacklogSummary,
    RemediationAction,
    RemediationExecutionReport,
    RemediationOwner,
    RemediationPlan,
    SlideLedger,
    SlideRange,
    StateCapsule,
    StateFilePointer,
    UpstreamFixPlan,
    UpstreamFixProposal,
    VizManifest,
    VizSpecSet,
    load_state_file,
    save_state_file,
)


class PostApplyClosureOutputs(ContractModel):
    closure_report: ClosureReport
    remaining_backlog: RemainingBacklog
    approval_packet: ApprovalPacketSet
    authoring_deltas: AuthoringDeltas
    upstream_fix_plan: UpstreamFixPlan
    state_capsule: StateCapsule
    handoff_packet: HandoffPacket | None = None
    batch_manifest: BatchManifest


_SEVERITY_RANK = {
    QASeverity.INFO: 0,
    QASeverity.MINOR: 1,
    QASeverity.MAJOR: 2,
    QASeverity.CRITICAL: 3,
}


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


def _canonical_state_root(state_capsule: StateCapsule, state_output_dir: Path, artifact_root: Path) -> str:
    if state_capsule.canonical_state_root:
        return state_capsule.canonical_state_root
    return _display_path(state_output_dir, artifact_root)


def _severity_for_actions(actions: list[RemediationAction]) -> QASeverity | None:
    if not actions:
        return None
    return max((action.severity for action in actions), key=lambda severity: _SEVERITY_RANK[severity])


def _owners_for_actions(actions: list[RemediationAction]) -> list[RemediationOwner]:
    seen: set[RemediationOwner] = set()
    ordered: list[RemediationOwner] = []
    for action in actions:
        if action.owner not in seen:
            seen.add(action.owner)
            ordered.append(action.owner)
    return ordered


def _stages_for_actions(actions: list[RemediationAction], fallback: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for stage in [stage for action in actions for stage in action.rerun_stages] + list(fallback):
        if stage and stage not in seen:
            seen.add(stage)
            ordered.append(stage)
    return ordered


def _packet_by_fix(approval_packet: ApprovalPacketSet) -> dict[str, ApprovalPacket]:
    mapping: dict[str, ApprovalPacket] = {}
    for packet in approval_packet.packets:
        for fix_id in packet.included_fix_ids:
            mapping[fix_id] = packet
    return mapping


def _action_lookup(remediation_plan: RemediationPlan) -> tuple[dict[str, RemediationAction], dict[str, list[RemediationAction]]]:
    by_id = {action.action_id: action for action in remediation_plan.actions}
    by_finding: dict[str, list[RemediationAction]] = {}
    for action in remediation_plan.actions:
        by_finding.setdefault(action.finding_id, []).append(action)
    return by_id, by_finding


def _range_for_action(action: RemediationAction, slide_ledger: SlideLedger) -> SlideRange:
    if action.slide_range is not None:
        return action.slide_range
    if action.slide_number is not None:
        return SlideRange(start=action.slide_number, end=action.slide_number)
    numbers = [entry.slide_number for entry in slide_ledger.entries]
    if not numbers:
        return SlideRange(start=1, end=1)
    return SlideRange(start=min(numbers), end=max(numbers))


def _section_ids_for_range(slide_ledger: SlideLedger, slide_range: SlideRange) -> list[str]:
    return _dedupe(
        [
            entry.section_id
            for entry in slide_ledger.entries
            if slide_range.start <= entry.slide_number <= slide_range.end and entry.section_id
        ]
    )


def _actions_for_fix(
    fix: UpstreamFixProposal,
    *,
    action_by_id: dict[str, RemediationAction],
    actions_by_finding: dict[str, list[RemediationAction]],
) -> list[RemediationAction]:
    ordered: list[RemediationAction] = []
    seen: set[str] = set()
    for action_id in fix.source_action_ids:
        action = action_by_id.get(action_id)
        if action is not None and action.action_id not in seen:
            seen.add(action.action_id)
            ordered.append(action)
    for finding_id in fix.source_finding_ids:
        for action in actions_by_finding.get(finding_id, []):
            if action.action_id not in seen:
                seen.add(action.action_id)
                ordered.append(action)
    return ordered


def _actions_for_blocked_issue(
    issue: BlockedManualUpstreamIssue,
    *,
    action_by_id: dict[str, RemediationAction],
    actions_by_finding: dict[str, list[RemediationAction]],
) -> list[RemediationAction]:
    ordered: list[RemediationAction] = []
    seen: set[str] = set()
    for action_id in issue.source_action_ids:
        action = action_by_id.get(action_id)
        if action is not None and action.action_id not in seen:
            seen.add(action.action_id)
            ordered.append(action)
    for finding_id in issue.source_finding_ids:
        for action in actions_by_finding.get(finding_id, []):
            if action.action_id not in seen:
                seen.add(action.action_id)
                ordered.append(action)
    return ordered


def _recommended_action_for_fix(status: ClosureReasonStatus, *, packet_id: str | None, fix_id: str) -> str:
    if status == ClosureReasonStatus.PENDING_APPROVAL:
        target = packet_id or fix_id
        return f"Review approval packet {target} and record an explicit approve or reject decision."
    if status == ClosureReasonStatus.DEFERRED:
        return f"Carry fix {fix_id} into the next bounded approval/apply cycle when the affected scope is reopened."
    if status == ClosureReasonStatus.FAILED_REVIEW_NEEDED:
        return f"Review the approved apply failure for fix {fix_id}, correct the deterministic delta selection or selector path, then rerun Phase 14."
    return f"No additional action is required for fix {fix_id} in the current closure cycle."


def _classify_fix(
    fix: UpstreamFixProposal,
    *,
    fix_result,
    open_finding_ids: set[str],
    remaining_pending_fix_ids: set[str],
) -> tuple[ClosureReasonStatus, list[str]]:
    approval_status = fix_result.approval_status if fix_result is not None else fix.approval_status
    apply_status = fix_result.apply_status if fix_result is not None else fix.apply_status
    notes: list[str] = []
    if apply_status == ApplyDecisionStatus.APPLIED:
        return ClosureReasonStatus.CLOSED_APPLIED, notes
    if approval_status == ApprovalDecisionStatus.REJECTED or apply_status == ApplyDecisionStatus.SKIPPED:
        notes.append("The fix is no longer actionable in the current approval lineage.")
        return ClosureReasonStatus.OBSOLETE_SUPERSEDED, notes
    if apply_status == ApplyDecisionStatus.FAILED:
        notes.append("The approved delta application failed and needs deterministic review before another rerun.")
        return ClosureReasonStatus.FAILED_REVIEW_NEEDED, notes
    if approval_status == ApprovalDecisionStatus.APPROVED and apply_status == ApplyDecisionStatus.BLOCKED:
        notes.append("The fix was approved but could not be closed safely from the current bounded delta set.")
        return ClosureReasonStatus.FAILED_REVIEW_NEEDED, notes
    if not any(finding_id in open_finding_ids for finding_id in fix.source_finding_ids) and fix.fix_id not in remaining_pending_fix_ids:
        notes.append("The source finding is no longer open in the current QA lineage.")
        return ClosureReasonStatus.OBSOLETE_SUPERSEDED, notes
    if approval_status == ApprovalDecisionStatus.PENDING:
        notes.append("The fix still needs explicit human approval.")
        return ClosureReasonStatus.PENDING_APPROVAL, notes
    if apply_status == ApplyDecisionStatus.DEFERRED:
        notes.append("The fix remains deferred for a later approved-apply run.")
        return ClosureReasonStatus.DEFERRED, notes
    if apply_status == ApplyDecisionStatus.BLOCKED:
        notes.append("The fix remains blocked after apply evaluation and needs review.")
        return ClosureReasonStatus.FAILED_REVIEW_NEEDED, notes
    notes.append("The fix remains unresolved in the current closure cycle.")
    return ClosureReasonStatus.DEFERRED, notes


def _classify_blocked_issue(
    issue: BlockedManualUpstreamIssue,
    *,
    open_finding_ids: set[str],
    remaining_blocked_issue_ids: set[str],
) -> tuple[ClosureReasonStatus, list[str]]:
    if issue.issue_id in remaining_blocked_issue_ids or any(finding_id in open_finding_ids for finding_id in issue.source_finding_ids):
        return ClosureReasonStatus.BLOCKED_MANUAL, [issue.blocked_reason]
    return ClosureReasonStatus.OBSOLETE_SUPERSEDED, ["The blocked issue no longer maps to an open finding in the current lineage."]


def _classify_deferred_action(action: RemediationAction, *, open_finding_ids: set[str]) -> tuple[ClosureReasonStatus, list[str]]:
    if action.finding_id in open_finding_ids:
        return ClosureReasonStatus.DEFERRED, ["The deferred action is still represented in the current QA backlog."]
    return ClosureReasonStatus.OBSOLETE_SUPERSEDED, ["The deferred action no longer maps to an open finding in the current QA backlog."]


def _packet_apply_status(packet: ApprovalPacket, fix_apply_statuses: list[ApplyDecisionStatus]) -> ApplyDecisionStatus:
    if not fix_apply_statuses:
        return packet.apply_status
    if any(status == ApplyDecisionStatus.FAILED for status in fix_apply_statuses):
        return ApplyDecisionStatus.FAILED
    if any(status == ApplyDecisionStatus.BLOCKED for status in fix_apply_statuses):
        return ApplyDecisionStatus.BLOCKED
    if all(status == ApplyDecisionStatus.SKIPPED for status in fix_apply_statuses):
        return ApplyDecisionStatus.SKIPPED
    if all(status == ApplyDecisionStatus.APPLIED for status in fix_apply_statuses):
        return ApplyDecisionStatus.APPLIED
    if packet.approval_status == ApprovalDecisionStatus.PENDING:
        return ApplyDecisionStatus.PENDING
    if any(status == ApplyDecisionStatus.DEFERRED for status in fix_apply_statuses):
        return ApplyDecisionStatus.DEFERRED
    return ApplyDecisionStatus.PENDING


def _build_fix_backlog_item(
    fix: UpstreamFixProposal,
    *,
    packet_id: str | None,
    status: ClosureReasonStatus,
    status_notes: list[str],
    actions: list[RemediationAction],
) -> RemainingBacklogItem:
    return RemainingBacklogItem(
        item_id=fix.fix_id,
        item_type=BacklogItemType.FIX,
        status=status,
        summary=fix.summary,
        fix_id=fix.fix_id,
        packet_id=packet_id,
        finding_ids=list(fix.source_finding_ids),
        source_action_ids=list(fix.source_action_ids),
        delta_ids=list(fix.delta_ids),
        severity=_severity_for_actions(actions),
        scope=fix.scope,
        owners=_owners_for_actions(actions),
        target_artifacts=list(fix.target_artifacts),
        affected_slide_range=fix.affected_slide_range,
        affected_batch_ids=list(fix.affected_batch_ids),
        affected_section_ids=list(fix.affected_section_ids),
        downstream_stages=_stages_for_actions(actions, fix.downstream_rerun_stages),
        recommended_next_action=_recommended_action_for_fix(status, packet_id=packet_id, fix_id=fix.fix_id),
        notes=[*status_notes, fix.rationale],
    )


def _build_blocked_backlog_item(
    issue: BlockedManualUpstreamIssue,
    *,
    status: ClosureReasonStatus,
    status_notes: list[str],
    actions: list[RemediationAction],
) -> RemainingBacklogItem:
    return RemainingBacklogItem(
        item_id=issue.issue_id,
        item_type=BacklogItemType.BLOCKED_MANUAL,
        status=status,
        summary=issue.summary,
        issue_id=issue.issue_id,
        finding_ids=list(issue.source_finding_ids),
        source_action_ids=list(issue.source_action_ids),
        severity=_severity_for_actions(actions),
        scope=issue.scope,
        owners=_owners_for_actions(actions),
        target_artifacts=list(issue.candidate_target_artifacts),
        affected_slide_range=issue.affected_slide_range,
        affected_batch_ids=list(issue.affected_batch_ids),
        affected_section_ids=list(issue.affected_section_ids),
        downstream_stages=_stages_for_actions(actions, issue.downstream_rerun_stages),
        recommended_next_action=issue.suggested_manual_next_step,
        notes=[*status_notes, issue.rationale],
    )


def _build_deferred_action_item(
    action: RemediationAction,
    *,
    status: ClosureReasonStatus,
    status_notes: list[str],
    slide_ledger: SlideLedger,
) -> RemainingBacklogItem:
    affected_range = _range_for_action(action, slide_ledger)
    return RemainingBacklogItem(
        item_id=action.action_id,
        item_type=BacklogItemType.FIX,
        status=status,
        summary=action.next_action,
        finding_ids=[action.finding_id],
        source_action_ids=[action.action_id],
        severity=action.severity,
        scope=action.scope,
        owners=[action.owner],
        affected_slide_range=affected_range,
        affected_batch_ids=[action.target_batch_id] if action.target_batch_id else [],
        affected_section_ids=_section_ids_for_range(slide_ledger, affected_range),
        downstream_stages=list(action.rerun_stages),
        recommended_next_action=action.next_action,
        notes=[*status_notes, action.rationale],
    )


def _count_map(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _build_remaining_backlog_summary(items: list[RemainingBacklogItem], *, total_items_considered: int) -> RemainingBacklogSummary:
    actionable_statuses = {
        ClosureReasonStatus.PENDING_APPROVAL,
        ClosureReasonStatus.DEFERRED,
        ClosureReasonStatus.BLOCKED_MANUAL,
        ClosureReasonStatus.FAILED_REVIEW_NEEDED,
    }
    return RemainingBacklogSummary(
        total_items_considered=total_items_considered,
        remaining_actionable_items=sum(1 for item in items if item.status in actionable_statuses),
        pending_approval_items=sum(1 for item in items if item.status == ClosureReasonStatus.PENDING_APPROVAL),
        deferred_items=sum(1 for item in items if item.status == ClosureReasonStatus.DEFERRED),
        blocked_manual_items=sum(1 for item in items if item.status == ClosureReasonStatus.BLOCKED_MANUAL),
        obsolete_superseded_items=sum(1 for item in items if item.status == ClosureReasonStatus.OBSOLETE_SUPERSEDED),
        failed_review_items=sum(1 for item in items if item.status == ClosureReasonStatus.FAILED_REVIEW_NEEDED),
        severity_counts=_count_map([item.severity.value for item in items if item.severity is not None]),
        scope_counts=_count_map([item.scope.value for item in items]),
        owner_counts=_count_map([owner.value for item in items for owner in item.owners]),
        stage_counts=_count_map([stage for item in items for stage in item.downstream_stages]),
    )


def _update_state_capsule(
    state_capsule: StateCapsule,
    *,
    pending_packet_ids: list[str],
    remaining_fix_ids: list[str],
    blocked_issue_ids: list[str],
    failed_fix_ids: list[str],
    actionable_backlog_count: int,
    open_issue_summaries: list[str],
    pointer_root: str,
) -> StateCapsule:
    file_pointers = list(state_capsule.file_pointers)
    for schema_name in ("closure_report", "remaining_backlog"):
        file_pointers = _upsert_pointer(
            file_pointers,
            schema_name=schema_name,
            path=f"{pointer_root}/{DEFAULT_STATE_FILENAMES[schema_name]}",
        )
    pending_actions = [
        *(f"Review approval packet {packet_id} before another approved-apply run." for packet_id in pending_packet_ids),
        *(f"Review blocked upstream issue {issue_id} manually before another upstream apply run." for issue_id in blocked_issue_ids),
        *(f"Review failed approved fix {fix_id} before another approved-apply run." for fix_id in failed_fix_ids),
    ]
    if not pending_actions:
        pending_actions = ["No remaining upstream backlog. Continue with final QA review or ship readiness checks."]
    return state_capsule.model_copy(
        update={
            "active_gate": WorkflowGate.PRODUCTION_AND_QA,
            "open_issues": _dedupe(open_issue_summaries),
            "pending_actions": _dedupe(pending_actions),
            "pending_approval_packet_ids": list(pending_packet_ids),
            "pending_upstream_fix_ids": list(remaining_fix_ids),
            "remediation_backlog_count": actionable_backlog_count,
            "file_pointers": file_pointers,
            "updated_at": datetime.now(UTC),
        }
    )


def _update_handoff_packet(
    handoff_packet: HandoffPacket,
    *,
    pending_packet_ids: list[str],
    remaining_fix_ids: list[str],
    blocked_issue_ids: list[str],
    failed_fix_ids: list[str],
    open_issue_summaries: list[str],
    pointer_root: str,
) -> HandoffPacket:
    file_pointers = list(handoff_packet.file_pointers)
    for schema_name in ("closure_report", "remaining_backlog"):
        file_pointers = _upsert_pointer(
            file_pointers,
            schema_name=schema_name,
            path=f"{pointer_root}/{DEFAULT_STATE_FILENAMES[schema_name]}",
        )
    produced = _dedupe(
        list(handoff_packet.produced_artifacts)
        + [
            DEFAULT_STATE_FILENAMES["approval_packet"],
            DEFAULT_STATE_FILENAMES["authoring_deltas"],
            DEFAULT_STATE_FILENAMES["upstream_fix_plan"],
            DEFAULT_STATE_FILENAMES["state_capsule"],
            DEFAULT_STATE_FILENAMES["handoff_packet"],
            DEFAULT_STATE_FILENAMES["closure_report"],
            DEFAULT_STATE_FILENAMES["remaining_backlog"],
        ]
    )
    reviewed = _dedupe(list(handoff_packet.reviewed_artifacts) + [DEFAULT_STATE_FILENAMES["closure_report"], DEFAULT_STATE_FILENAMES["remaining_backlog"]])
    instructions = [
        *(f"Resolve approval packet {packet_id} before another approved-apply run." for packet_id in pending_packet_ids),
        *(f"Resolve blocked upstream issue {issue_id} manually before another approved-apply run." for issue_id in blocked_issue_ids),
        *(f"Review failed approved fix {fix_id} before another approved-apply run." for fix_id in failed_fix_ids),
    ]
    if not instructions:
        instructions = ["No remaining upstream backlog. Continue with final QA review or ship readiness checks."]
    return handoff_packet.model_copy(
        update={
            "file_pointers": file_pointers,
            "produced_artifacts": produced,
            "reviewed_artifacts": reviewed,
            "open_issues": _dedupe(open_issue_summaries),
            "verification_items_open": _dedupe(
                [f"Approval packet {packet_id}" for packet_id in pending_packet_ids]
                + [f"Blocked upstream issue {issue_id}" for issue_id in blocked_issue_ids]
                + [f"Failed approved fix {fix_id}" for fix_id in failed_fix_ids]
            ),
            "pending_approval_packet_ids": list(pending_packet_ids),
            "pending_upstream_fix_ids": list(remaining_fix_ids),
            "handoff_instructions": _dedupe(instructions),
            "generated_at": datetime.now(UTC),
        }
    )


def close_approved_fixes(
    *,
    approved_apply_report: ApprovedApplyReport,
    approval_packet: ApprovalPacketSet,
    authoring_deltas: AuthoringDeltas,
    upstream_fix_plan: UpstreamFixPlan,
    remediation_plan: RemediationPlan,
    remediation_execution_report: RemediationExecutionReport,
    batch_manifest: BatchManifest,
    context_lock: ContextLock,
    handoff_packet: HandoffPacket,
    state_capsule: StateCapsule,
    slide_ledger: SlideLedger,
    slide_build_linkage: SlideBuildLinkage,
    qa_report: QAReport,
    build_manifest: BuildManifest,
    blueprint: Blueprint,
    design_system: DesignSystem,
    deck_constitution: DeckConstitution,
    layout_library: LayoutLibrary,
    asset_manifest: AssetManifest,
    viz_manifest: VizManifest,
    asset_requests: AssetRequests | None = None,
    viz_spec: VizSpecSet | None = None,
    pointer_root: str | None = None,
) -> PostApplyClosureOutputs:
    del remediation_execution_report
    del context_lock
    del slide_build_linkage
    del build_manifest
    del blueprint
    del design_system
    del deck_constitution
    del layout_library
    del asset_manifest
    del viz_manifest
    del asset_requests
    del viz_spec

    action_by_id, actions_by_finding = _action_lookup(remediation_plan)
    packet_by_fix = _packet_by_fix(approval_packet)
    fix_result_by_id = {result.fix_id: result for result in approved_apply_report.fix_results}
    delta_result_by_id = {
        delta_result.delta_id: delta_result
        for result in approved_apply_report.fix_results
        for delta_result in result.delta_results
    }
    open_findings = [finding for finding in qa_report.findings if finding.status.value == "open"]
    open_finding_ids = {finding.finding_id for finding in open_findings}
    remaining_pending_fix_ids = set(approved_apply_report.remaining_pending_fix_ids)
    remaining_blocked_issue_ids = set(approved_apply_report.remaining_blocked_issue_ids)
    pointer_root_value = pointer_root or state_capsule.canonical_state_root or "."

    lineage_warnings: list[str] = []
    updated_deltas: list[AuthoringDeltaRecord] = []
    for delta in authoring_deltas.deltas:
        delta_result = delta_result_by_id.get(delta.delta_id)
        if delta_result is None:
            lineage_warnings.append(f"authoring delta {delta.delta_id} is missing from approved_apply_report.")
            updated_deltas.append(delta)
            continue
        updated_deltas.append(
            delta.model_copy(
                update={
                    "approval_status": delta_result.approval_status,
                    "apply_status": delta_result.apply_status,
                    "selected_option_id": delta_result.selected_option_id,
                }
            )
        )
        if sorted(delta.source_finding_ids) != sorted(delta_result.finding_ids):
            lineage_warnings.append(f"delta {delta.delta_id} finding lineage differs between authoring_deltas and approved_apply_report.")
    updated_authoring_deltas = authoring_deltas.model_copy(update={"deltas": updated_deltas})

    fix_closure_by_id: dict[str, ClosureReasonStatus] = {}
    fix_packet_ids: dict[str, str | None] = {}
    updated_fixes: list[UpstreamFixProposal] = []
    remaining_items: list[RemainingBacklogItem] = []
    closed_fix_ids: list[str] = []
    obsolete_fix_ids: list[str] = []
    failed_fix_ids: list[str] = []
    closure_reason_values: list[str] = []

    for fix in upstream_fix_plan.fixes:
        fix_result = fix_result_by_id.get(fix.fix_id)
        if fix_result is None:
            lineage_warnings.append(f"upstream fix {fix.fix_id} is missing from approved_apply_report.")
        else:
            if sorted(fix.source_finding_ids) != sorted(fix_result.finding_ids):
                lineage_warnings.append(f"fix {fix.fix_id} finding lineage differs between upstream_fix_plan and approved_apply_report.")
        packet = packet_by_fix.get(fix.fix_id)
        if packet is None:
            lineage_warnings.append(f"upstream fix {fix.fix_id} is missing an approval packet linkage.")
        fix_packet_ids[fix.fix_id] = packet.packet_id if packet is not None else None
        updated_fix = fix.model_copy(
            update={
                "approval_status": fix_result.approval_status if fix_result is not None else fix.approval_status,
                "apply_status": fix_result.apply_status if fix_result is not None else fix.apply_status,
            }
        )
        updated_fixes.append(updated_fix)
        closure_status, status_notes = _classify_fix(
            updated_fix,
            fix_result=fix_result,
            open_finding_ids=open_finding_ids,
            remaining_pending_fix_ids=remaining_pending_fix_ids,
        )
        fix_closure_by_id[fix.fix_id] = closure_status
        closure_reason_values.append(closure_status.value)
        if closure_status == ClosureReasonStatus.CLOSED_APPLIED:
            closed_fix_ids.append(fix.fix_id)
            continue
        if closure_status == ClosureReasonStatus.OBSOLETE_SUPERSEDED:
            obsolete_fix_ids.append(fix.fix_id)
        if closure_status == ClosureReasonStatus.FAILED_REVIEW_NEEDED:
            failed_fix_ids.append(fix.fix_id)
        remaining_items.append(
            _build_fix_backlog_item(
                updated_fix,
                packet_id=packet.packet_id if packet is not None else None,
                status=closure_status,
                status_notes=status_notes,
                actions=_actions_for_fix(updated_fix, action_by_id=action_by_id, actions_by_finding=actions_by_finding),
            )
        )

    blocked_issue_ids: list[str] = []
    for issue in upstream_fix_plan.blocked_manual_items:
        closure_status, status_notes = _classify_blocked_issue(
            issue,
            open_finding_ids=open_finding_ids,
            remaining_blocked_issue_ids=remaining_blocked_issue_ids,
        )
        closure_reason_values.append(closure_status.value)
        if closure_status == ClosureReasonStatus.BLOCKED_MANUAL:
            blocked_issue_ids.append(issue.issue_id)
        remaining_items.append(
            _build_blocked_backlog_item(
                issue,
                status=closure_status,
                status_notes=status_notes,
                actions=_actions_for_blocked_issue(issue, action_by_id=action_by_id, actions_by_finding=actions_by_finding),
            )
        )

    for action_id in upstream_fix_plan.deferred_or_noop_action_ids:
        action = action_by_id.get(action_id)
        if action is None:
            lineage_warnings.append(f"deferred action {action_id} is missing from remediation_plan.")
            continue
        closure_status, status_notes = _classify_deferred_action(action, open_finding_ids=open_finding_ids)
        closure_reason_values.append(closure_status.value)
        remaining_items.append(
            _build_deferred_action_item(
                action,
                status=closure_status,
                status_notes=status_notes,
                slide_ledger=slide_ledger,
            )
        )

    updated_packets: list[ApprovalPacket] = []
    closed_packet_ids: list[str] = []
    still_open_packet_ids: list[str] = []
    pending_packet_ids: list[str] = []
    for packet in approval_packet.packets:
        included_statuses = [
            next((fix.apply_status for fix in updated_fixes if fix.fix_id == fix_id), ApplyDecisionStatus.PENDING)
            for fix_id in packet.included_fix_ids
        ]
        updated_packet = packet.model_copy(update={"apply_status": _packet_apply_status(packet, included_statuses)})
        updated_packets.append(updated_packet)
        included_closure = [fix_closure_by_id.get(fix_id, ClosureReasonStatus.PENDING_APPROVAL) for fix_id in packet.included_fix_ids]
        if any(status in {ClosureReasonStatus.PENDING_APPROVAL, ClosureReasonStatus.DEFERRED, ClosureReasonStatus.FAILED_REVIEW_NEEDED} for status in included_closure):
            still_open_packet_ids.append(packet.packet_id)
        else:
            closed_packet_ids.append(packet.packet_id)
        if updated_packet.approval_status == ApprovalDecisionStatus.PENDING:
            pending_packet_ids.append(packet.packet_id)
    updated_approval_packet = approval_packet.model_copy(update={"packets": updated_packets})

    summary = _build_remaining_backlog_summary(remaining_items, total_items_considered=len(upstream_fix_plan.fixes) + len(upstream_fix_plan.blocked_manual_items) + len(upstream_fix_plan.deferred_or_noop_action_ids))
    remaining_fix_ids = [
        item.fix_id
        for item in remaining_items
        if item.fix_id is not None and item.status in {ClosureReasonStatus.PENDING_APPROVAL, ClosureReasonStatus.DEFERRED, ClosureReasonStatus.FAILED_REVIEW_NEEDED}
    ]
    recommendations = _dedupe([item.recommended_next_action for item in remaining_items if item.status != ClosureReasonStatus.OBSOLETE_SUPERSEDED])
    if not recommendations:
        recommendations = ["No remaining upstream backlog. Continue with final QA review or ship readiness checks."]
    remaining_backlog = RemainingBacklog(
        backlog_id=f"remaining-backlog-{approved_apply_report.report_id}",
        deck_title=approved_apply_report.deck_title,
        source_plan_id=upstream_fix_plan.plan_id,
        source_execution_report_id=upstream_fix_plan.source_execution_report_id,
        source_approved_apply_report_id=approved_apply_report.report_id,
        summary=summary,
        items=remaining_items,
        recommended_next_actions=recommendations,
        pending_packet_ids=pending_packet_ids,
        remaining_fix_ids=remaining_fix_ids,
        blocked_issue_ids=blocked_issue_ids,
        canonical_state_root=pointer_root_value,
        warnings=list(lineage_warnings),
        notes=["Remaining backlog excludes fixes that already closed as applied; see closure-report.json for archived packet lineage."],
    )

    open_issue_summaries = _dedupe(
        [finding.summary for finding in open_findings]
        + [f"Approval packet {packet_id} is still pending." for packet_id in pending_packet_ids]
        + [f"Blocked upstream issue {issue_id} still needs manual review." for issue_id in blocked_issue_ids]
        + [f"Approved fix {fix_id} needs deterministic review before another apply run." for fix_id in failed_fix_ids]
    )
    updated_state_capsule = _update_state_capsule(
        state_capsule,
        pending_packet_ids=pending_packet_ids,
        remaining_fix_ids=remaining_fix_ids,
        blocked_issue_ids=blocked_issue_ids,
        failed_fix_ids=failed_fix_ids,
        actionable_backlog_count=summary.remaining_actionable_items,
        open_issue_summaries=open_issue_summaries,
        pointer_root=pointer_root_value,
    )
    updated_handoff_packet = _update_handoff_packet(
        handoff_packet,
        pending_packet_ids=pending_packet_ids,
        remaining_fix_ids=remaining_fix_ids,
        blocked_issue_ids=blocked_issue_ids,
        failed_fix_ids=failed_fix_ids,
        open_issue_summaries=open_issue_summaries,
        pointer_root=pointer_root_value,
    )
    updated_upstream_fix_plan = upstream_fix_plan.model_copy(
        update={
            "actionable_upstream_issue_count": len(remaining_fix_ids),
            "blocked_manual_count": len(blocked_issue_ids),
            "fixes": updated_fixes,
            "approval_packets": updated_packets,
        }
    )
    canonical_artifacts = [
        DEFAULT_STATE_FILENAMES["approval_packet"],
        DEFAULT_STATE_FILENAMES["authoring_deltas"],
        DEFAULT_STATE_FILENAMES["upstream_fix_plan"],
        DEFAULT_STATE_FILENAMES["state_capsule"],
        DEFAULT_STATE_FILENAMES["handoff_packet"],
        DEFAULT_STATE_FILENAMES["closure_report"],
        DEFAULT_STATE_FILENAMES["remaining_backlog"],
    ]
    closure_report = ClosureReport(
        report_id=f"closure-{approved_apply_report.report_id}",
        deck_title=approved_apply_report.deck_title,
        source_plan_id=upstream_fix_plan.plan_id,
        source_execution_report_id=upstream_fix_plan.source_execution_report_id,
        source_approved_apply_report_id=approved_apply_report.report_id,
        summary=ClosureReportSummary(
            total_approval_packets_seen=len(updated_packets),
            closed_packet_count=len(closed_packet_ids),
            still_open_packet_count=len(still_open_packet_ids),
            delta_counts_by_status=_count_map([delta.apply_status.value for delta in updated_authoring_deltas.deltas]),
            item_counts_by_closure_reason=_count_map(closure_reason_values),
        ),
        closed_packet_ids=closed_packet_ids,
        still_open_packet_ids=still_open_packet_ids,
        closed_fix_ids=closed_fix_ids,
        remaining_fix_ids=remaining_fix_ids,
        blocked_issue_ids=blocked_issue_ids,
        obsolete_fix_ids=obsolete_fix_ids,
        archived_packet_ids=list(closed_packet_ids),
        lineage_integrity_ok=not lineage_warnings,
        lineage_warnings=list(lineage_warnings),
        canonical_artifacts_refreshed=canonical_artifacts,
        warnings=list(lineage_warnings),
        notes=["Closure report doubles as the archive reference for applied packets in the current control model."],
        recommendations=recommendations,
        safe_partial_rerun_tightening_applied=False,
        safe_partial_rerun_notes=["No narrower compile or QA isolation path is proven safe yet; conservative worker-level reruns remain in effect."],
        canonical_state_root=pointer_root_value,
    )
    return PostApplyClosureOutputs(
        closure_report=closure_report,
        remaining_backlog=remaining_backlog,
        approval_packet=updated_approval_packet,
        authoring_deltas=updated_authoring_deltas,
        upstream_fix_plan=updated_upstream_fix_plan,
        state_capsule=updated_state_capsule,
        handoff_packet=updated_handoff_packet,
        batch_manifest=batch_manifest,
    )


def close_approved_fixes_from_files(
    approved_apply_report_path: str | Path,
    approval_packet_path: str | Path,
    authoring_deltas_path: str | Path,
    upstream_fix_plan_path: str | Path,
    remediation_plan_path: str | Path,
    remediation_execution_report_path: str | Path,
    batch_manifest_path: str | Path,
    context_lock_path: str | Path,
    handoff_packet_path: str | Path,
    state_capsule_path: str | Path,
    slide_ledger_path: str | Path,
    slide_build_linkage_path: str | Path,
    qa_report_path: str | Path,
    build_manifest_path: str | Path,
    blueprint_path: str | Path,
    design_system_path: str | Path,
    deck_constitution_path: str | Path,
    layout_library_path: str | Path,
    asset_manifest_path: str | Path,
    viz_manifest_path: str | Path,
    *,
    asset_requests_path: str | Path | None = None,
    viz_spec_path: str | Path | None = None,
    pointer_root: str | None = None,
) -> PostApplyClosureOutputs:
    approved_apply_report = load_state_file(approved_apply_report_path)
    approval_packet = load_state_file(approval_packet_path)
    authoring_deltas = load_state_file(authoring_deltas_path)
    upstream_fix_plan = load_state_file(upstream_fix_plan_path)
    remediation_plan = load_state_file(remediation_plan_path)
    remediation_execution_report = load_state_file(remediation_execution_report_path)
    batch_manifest = load_state_file(batch_manifest_path)
    context_lock = load_state_file(context_lock_path)
    handoff_packet = load_state_file(handoff_packet_path)
    state_capsule = load_state_file(state_capsule_path)
    slide_ledger = load_state_file(slide_ledger_path)
    qa_report = load_state_file(qa_report_path)
    blueprint = load_state_file(blueprint_path)
    design_system = load_state_file(design_system_path)
    deck_constitution = load_state_file(deck_constitution_path)
    layout_library = load_state_file(layout_library_path)
    asset_manifest = load_state_file(asset_manifest_path)
    viz_manifest = load_state_file(viz_manifest_path)
    build_manifest = load_pptx_compile_file(build_manifest_path)
    slide_build_linkage = load_pptx_compile_file(slide_build_linkage_path)
    asset_requests = load_state_file(asset_requests_path) if asset_requests_path is not None and Path(asset_requests_path).is_file() else None
    viz_spec = load_state_file(viz_spec_path) if viz_spec_path is not None and Path(viz_spec_path).is_file() else None

    expected = [
        (approved_apply_report, "approved_apply_report"),
        (approval_packet, "approval_packet"),
        (authoring_deltas, "authoring_deltas"),
        (upstream_fix_plan, "upstream_fix_plan"),
        (remediation_plan, "remediation_plan"),
        (remediation_execution_report, "remediation_execution_report"),
        (batch_manifest, "batch_manifest"),
        (context_lock, "context_lock"),
        (handoff_packet, "handoff_packet"),
        (state_capsule, "state_capsule"),
        (slide_ledger, "slide_ledger"),
        (qa_report, "qa_report"),
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
    if asset_requests is not None and asset_requests.schema_name != "asset_requests":
        raise TypeError(f"expected asset_requests, found {asset_requests.schema_name}")
    if viz_spec is not None and viz_spec.schema_name != "viz_spec":
        raise TypeError(f"expected viz_spec, found {viz_spec.schema_name}")

    return close_approved_fixes(
        approved_apply_report=approved_apply_report,
        approval_packet=approval_packet,
        authoring_deltas=authoring_deltas,
        upstream_fix_plan=upstream_fix_plan,
        remediation_plan=remediation_plan,
        remediation_execution_report=remediation_execution_report,
        batch_manifest=batch_manifest,
        context_lock=context_lock,
        handoff_packet=handoff_packet,
        state_capsule=state_capsule,
        slide_ledger=slide_ledger,
        slide_build_linkage=slide_build_linkage,
        qa_report=qa_report,
        build_manifest=build_manifest,
        blueprint=blueprint,
        design_system=design_system,
        deck_constitution=deck_constitution,
        layout_library=layout_library,
        asset_manifest=asset_manifest,
        viz_manifest=viz_manifest,
        asset_requests=asset_requests,
        viz_spec=viz_spec,
        pointer_root=pointer_root,
    )


def write_post_apply_closure_outputs(outputs: PostApplyClosureOutputs, output_dir: str | Path) -> dict[str, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    written = {
        "closure_report": save_state_file(outputs.closure_report, root / DEFAULT_STATE_FILENAMES["closure_report"]),
        "remaining_backlog": save_state_file(outputs.remaining_backlog, root / DEFAULT_STATE_FILENAMES["remaining_backlog"]),
        "approval_packet": save_state_file(outputs.approval_packet, root / DEFAULT_STATE_FILENAMES["approval_packet"]),
        "authoring_deltas": save_state_file(outputs.authoring_deltas, root / DEFAULT_STATE_FILENAMES["authoring_deltas"]),
        "upstream_fix_plan": save_state_file(outputs.upstream_fix_plan, root / DEFAULT_STATE_FILENAMES["upstream_fix_plan"]),
        "state_capsule": save_state_file(outputs.state_capsule, root / DEFAULT_STATE_FILENAMES["state_capsule"]),
    }
    if outputs.handoff_packet is not None:
        written["handoff_packet"] = save_state_file(outputs.handoff_packet, root / DEFAULT_STATE_FILENAMES["handoff_packet"])
    return written


