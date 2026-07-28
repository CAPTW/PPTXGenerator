"""Bounded remediation execution and targeted downstream refresh."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from ..compat.legacy_non_pptx import WorkflowGate
from .deck_qa import run_deck_qa
from .large_deck_orchestration import orchestrate_large_deck
from ..pptx_compiler import BuildManifest, SlideBuildLinkage, compile_pptx, load_pptx_compile_file
from ..compat.legacy_non_pptx import (
    AssetKind,
    AssetManifest,
    AssetRecord,
    AssetRequests,
    AssetStatus,
    BatchManifest,
    Blueprint,
    ContextLock,
    ContractModel,
    DEFAULT_STATE_FILENAMES,
    DeckConstitution,
    DesignSystem,
    FindingStatus,
    HandoffPacket,
    LayoutLibrary,
    QAGovernance,
    QAReport,
    QASeverity,
    QAStatus,
    QASlideResult,
    QASummary,
    RemediationAction,
    RemediationDisposition,
    RemediationExecutionAction,
    RemediationExecutionItem,
    RemediationExecutionReport,
    RemediationExecutionStatus,
    RemediationExecutionSummary,
    RemediationPlan,
    RemediationScope,
    RemediationSummary,
    SlideLedger,
    SlideLedgerEntry,
    StageStatus,
    StateCapsule,
    StateFilePointer,
    VizManifest,
    VizRecord,
    VizSpecSet,
    load_state_file,
    save_state_file,
)
from .structured_visuals import run_structured_visuals
from .workflow_planner import WorkflowPlan


RERUN_STAGE_ORDER = [
    "render-visuals",
    "compile-pptx",
    "qa-deck",
    "orchestrate-large-deck",
]

SAFE_AUTO_ACTIONS = {
    RemediationExecutionAction.SYNC_STATUS_ONLY,
    RemediationExecutionAction.APPLY_KNOWN_FALLBACK,
    RemediationExecutionAction.PROMOTE_EXISTING_ALTERNATE_ASSET,
    RemediationExecutionAction.PROMOTE_SIMPLIFIED_STRUCTURED_VISUAL,
    RemediationExecutionAction.DROP_BLOCKED_DENSE_VISUAL,
    RemediationExecutionAction.RERUN_COMPILER,
    RemediationExecutionAction.RERUN_QA,
    RemediationExecutionAction.MARK_DEFERRED,
    RemediationExecutionAction.MARK_BLOCKED,
    RemediationExecutionAction.MARK_REQUIRES_UPSTREAM_CHANGE,
}


class RemediationExecutionOutputs(ContractModel):
    remediation_execution_report: RemediationExecutionReport
    asset_manifest: AssetManifest
    viz_manifest: VizManifest
    build_manifest: BuildManifest
    qa_report: QAReport
    qa_governance: QAGovernance | None = None
    slide_ledger: SlideLedger
    slide_build_linkage: SlideBuildLinkage
    batch_manifest: BatchManifest
    context_lock: ContextLock
    handoff_packet: HandoffPacket | None = None
    state_capsule: StateCapsule
    remediation_plan: RemediationPlan
    pptx_path: Path | None = None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def _clone_model(model):
    return model.__class__.model_validate(model.model_dump(mode="json", exclude_none=True))


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _resolve_path(path_text: str | None, artifact_root: Path) -> Path | None:
    if not path_text:
        return None
    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate
    return (artifact_root / candidate).resolve()


def _canonical_state_root(state_capsule: StateCapsule | None, state_output_dir: Path, artifact_root: Path) -> str:
    if state_capsule is not None and state_capsule.canonical_state_root:
        return state_capsule.canonical_state_root
    return _display_path(state_output_dir, artifact_root)


def _upsert_pointer(
    pointers: list[StateFilePointer],
    *,
    schema_name: str,
    path: str,
) -> list[StateFilePointer]:
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


def _finding_status_for_item(item: RemediationExecutionItem) -> FindingStatus:
    if item.execution_status == RemediationExecutionStatus.APPLIED:
        return FindingStatus.RESOLVED
    if item.execution_status == RemediationExecutionStatus.DEFERRED:
        return FindingStatus.WAIVED
    return FindingStatus.OPEN


def _report_status(findings) -> QAStatus:
    if any(finding.severity in {QASeverity.CRITICAL, QASeverity.MAJOR} for finding in findings if finding.status == FindingStatus.OPEN):
        return QAStatus.FAIL
    return QAStatus.CONDITIONAL_PASS if findings else QAStatus.PASS


def _slide_findings_by_number(qa_report: QAReport, slide_ledger: SlideLedger) -> dict[int, list]:
    findings_by_slide: dict[int, list] = {}
    slide_numbers = {entry.slide_number for entry in slide_ledger.entries}
    for finding in qa_report.findings:
        if finding.slide_number is not None and finding.slide_number in slide_numbers:
            findings_by_slide.setdefault(finding.slide_number, []).append(finding)
            continue
        if finding.slide_range is not None:
            for slide_number in range(finding.slide_range.start, finding.slide_range.end + 1):
                if slide_number in slide_numbers:
                    findings_by_slide.setdefault(slide_number, []).append(finding)
    return findings_by_slide


def _rebuild_qa_report(
    qa_report: QAReport,
    slide_ledger: SlideLedger,
    slide_build_linkage: SlideBuildLinkage,
) -> tuple[QAReport, SlideLedger, SlideBuildLinkage]:
    findings_by_slide = _slide_findings_by_number(qa_report, slide_ledger)
    linkage_by_number = {slide.slide_number: slide for slide in slide_build_linkage.slides}
    updated_entries: list[SlideLedgerEntry] = []
    updated_links = []
    slide_results: list[QASlideResult] = []

    for entry in slide_ledger.entries:
        entry_findings = findings_by_slide.get(entry.slide_number, [])
        blocking_count = sum(1 for finding in entry_findings if finding.blocking and finding.status == FindingStatus.OPEN)
        warning_count = sum(1 for finding in entry_findings if not finding.blocking or finding.status != FindingStatus.OPEN)
        status = _report_status(entry_findings)
        updated_entries.append(
            entry.model_copy(
                update={
                    "qa_status": status,
                    "unresolved_blockers": _dedupe(
                        [*(entry.unresolved_blockers or []), *[finding.summary for finding in entry_findings if finding.blocking and finding.status == FindingStatus.OPEN]]
                    )
                    or None,
                }
            )
        )
        link = linkage_by_number.get(entry.slide_number)
        slide_results.append(
            QASlideResult(
                slide_number=entry.slide_number,
                slide_id=entry.slide_id,
                qa_status=status,
                layout_pattern_id=entry.layout_pattern_id,
                compile_status=entry.compile_status,
                build_link_index=link.pptx_index if link is not None else None,
                finding_ids=[finding.finding_id for finding in entry_findings],
                warning_count=warning_count,
                blocking_count=blocking_count,
                tags=_dedupe([tag for finding in entry_findings for tag in finding.tags]),
            )
        )

    for link in slide_build_linkage.slides:
        link_findings = findings_by_slide.get(link.slide_number, [])
        blocking_count = sum(1 for finding in link_findings if finding.blocking and finding.status == FindingStatus.OPEN)
        warning_count = sum(1 for finding in link_findings if not finding.blocking or finding.status != FindingStatus.OPEN)
        status = _report_status(link_findings)
        updated_links.append(
            link.model_copy(
                update={
                    "qa_status": status,
                    "qa_warning_count": warning_count,
                    "qa_blocking_count": blocking_count,
                    "qa_finding_ids": [finding.finding_id for finding in link_findings],
                    "qa_notes": [finding.summary for finding in link_findings[:3]],
                }
            )
        )

    rebuilt_findings = list(qa_report.findings)
    rebuilt_report = qa_report.model_copy(
        update={
            "qa_status": _report_status(rebuilt_findings),
            "summary": QASummary(
                slide_count=len(slide_ledger.entries),
                finding_count=len(rebuilt_findings),
                blocking_count=sum(1 for finding in rebuilt_findings if finding.blocking and finding.status == FindingStatus.OPEN),
                severity_counts=dict(Counter(finding.severity.value for finding in rebuilt_findings)),
                layer_counts=dict(Counter(finding.qa_layer.value for finding in rebuilt_findings)),
                recommendation_counts=dict(Counter(finding.recommendation_type.value for finding in rebuilt_findings)),
                pass_slide_count=sum(1 for result in slide_results if result.qa_status == QAStatus.PASS),
                conditional_slide_count=sum(1 for result in slide_results if result.qa_status == QAStatus.CONDITIONAL_PASS),
                fail_slide_count=sum(1 for result in slide_results if result.qa_status == QAStatus.FAIL),
            ),
            "slide_results": slide_results,
            "recommended_actions": _dedupe([finding.recommendation for finding in rebuilt_findings if finding.status == FindingStatus.OPEN]),
            "stop_condition_reached": _report_status(rebuilt_findings) == QAStatus.FAIL and qa_report.bounded_round >= qa_report.max_rounds,
        }
    )
    return (
        rebuilt_report,
        slide_ledger.model_copy(update={"entries": updated_entries}),
        slide_build_linkage.model_copy(update={"slides": updated_links}),
    )


def _remaining_plan(plan: RemediationPlan, execution_items: list[RemediationExecutionItem], qa_report: QAReport) -> RemediationPlan:
    status_by_action = {item.action_id: item.execution_status for item in execution_items}
    remaining_actions = [
        action
        for action in plan.actions
        if status_by_action.get(action.action_id) != RemediationExecutionStatus.APPLIED
    ]
    remaining_batches = [
        batch for batch in plan.fix_batches if any(finding_id in {action.finding_id for action in remaining_actions} for finding_id in batch.finding_ids)
    ]
    owner_counts = Counter(action.owner.value for action in remaining_actions)
    disposition_counts = Counter(action.disposition.value for action in remaining_actions)
    deferred_ids = [action.finding_id for action in remaining_actions if action.disposition == RemediationDisposition.SAFE_TO_DEFER]
    blocking_ids = [action.finding_id for action in remaining_actions if action.blocking]
    return plan.model_copy(
        update={
            "qa_status": qa_report.qa_status,
            "ship_blocked": bool(blocking_ids),
            "safe_to_ship_with_deferrals": bool(remaining_actions) and not blocking_ids and all(action.disposition == RemediationDisposition.SAFE_TO_DEFER for action in remaining_actions),
            "summary": RemediationSummary(
                actionable_count=len(remaining_actions),
                blocking_count=len(blocking_ids),
                deferred_count=len(deferred_ids),
                local_change_count=sum(
                    1 for action in remaining_actions if action.scope == RemediationScope.LOCAL_CHANGE_ONLY
                ),
                section_reflow_count=sum(
                    1 for action in remaining_actions if action.scope == RemediationScope.SECTION_LEVEL_REFLOW
                ),
                deck_reflow_count=sum(
                    1 for action in remaining_actions if action.scope == RemediationScope.DECK_LEVEL_REFLOW
                ),
                owner_counts=dict(owner_counts),
                disposition_counts=dict(disposition_counts),
            ),
            "actions": remaining_actions,
            "fix_batches": remaining_batches,
            "deferred_finding_ids": deferred_ids,
            "blocking_finding_ids": blocking_ids,
            "next_recommended_batch_id": remaining_batches[0].batch_id if remaining_batches else None,
        }
    )


def _update_context_lock(context_lock: ContextLock, qa_report: QAReport) -> ContextLock:
    blockers = [finding.summary for finding in qa_report.findings if finding.blocking and finding.status == FindingStatus.OPEN]
    risks = _dedupe(list(context_lock.unresolved_risks) + blockers)
    return context_lock.model_copy(
        update={
            "qa_blockers": blockers,
            "unresolved_risks": risks,
            "updated_at": datetime.now(UTC),
        }
    )


def _update_state_capsule(
    state_capsule: StateCapsule,
    qa_report: QAReport,
    remediation_plan: RemediationPlan,
    *,
    execution_report_path: str,
) -> StateCapsule:
    pending_actions = [action.next_action for action in remediation_plan.actions]
    if not pending_actions:
        pending_actions = ["No active remediation actions remain."]
    file_pointers = _upsert_pointer(
        list(state_capsule.file_pointers),
        schema_name="remediation_execution_report",
        path=execution_report_path,
    )
    return state_capsule.model_copy(
        update={
            "active_gate": WorkflowGate.PRODUCTION_AND_QA,
            "open_issues": _dedupe([finding.summary for finding in qa_report.findings if finding.status == FindingStatus.OPEN]),
            "pending_actions": _dedupe(pending_actions),
            "remediation_backlog_count": len(remediation_plan.actions),
            "file_pointers": file_pointers,
            "updated_at": datetime.now(UTC),
        }
    )


def _update_handoff_packet(
    handoff_packet: HandoffPacket,
    qa_report: QAReport,
    remediation_plan: RemediationPlan,
    *,
    execution_report_name: str,
) -> HandoffPacket:
    return handoff_packet.model_copy(
        update={
            "reviewed_artifacts": _dedupe(list(handoff_packet.reviewed_artifacts) + [execution_report_name, DEFAULT_STATE_FILENAMES["qa_report"]]),
            "open_issues": _dedupe([finding.summary for finding in qa_report.findings if finding.status == FindingStatus.OPEN]),
            "verification_items_open": _dedupe([finding.recommendation for finding in qa_report.findings if finding.blocking and finding.status == FindingStatus.OPEN]),
            "handoff_instructions": _dedupe(
                list(handoff_packet.handoff_instructions)
                + (
                    ["Continue with the remaining remediation backlog before the next ship candidate."]
                    if remediation_plan.actions
                    else ["No active remediation actions remain in the canonical state package."]
                )
            ),
            "next_recommended_batch_id": remediation_plan.next_recommended_batch_id or handoff_packet.next_recommended_batch_id,
            "generated_at": datetime.now(UTC),
        }
    )


def _match_action_assets(asset_manifest: AssetManifest, action: RemediationAction) -> list[AssetRecord]:
    matched: list[AssetRecord] = []
    for asset in asset_manifest.assets:
        if action.slide_id is not None and asset.slide_id == action.slide_id:
            matched.append(asset)
        elif action.slide_number is not None and asset.slide_number == action.slide_number:
            matched.append(asset)
        elif action.slide_range is not None and action.slide_range.start <= asset.slide_number <= action.slide_range.end:
            matched.append(asset)
    return matched


def _match_action_viz(viz_manifest: VizManifest, action: RemediationAction) -> list[VizRecord]:
    matched: list[VizRecord] = []
    for record in viz_manifest.visuals:
        if action.slide_id is not None and record.spec.slide_id == action.slide_id:
            matched.append(record)
        elif action.slide_number is not None and record.spec.slide_number == action.slide_number:
            matched.append(record)
        elif action.slide_range is not None and action.slide_range.start <= record.spec.slide_number <= action.slide_range.end:
            matched.append(record)
    return matched


def _status_for_execution(execution_status: RemediationExecutionStatus) -> StageStatus:
    if execution_status == RemediationExecutionStatus.APPLIED:
        return StageStatus.COMPLETE
    if execution_status == RemediationExecutionStatus.DEFERRED:
        return StageStatus.READY
    if execution_status in {RemediationExecutionStatus.BLOCKED, RemediationExecutionStatus.FAILED}:
        return StageStatus.BLOCKED
    return StageStatus.DRAFT


def _sync_remediation_metadata(
    slide_ledger: SlideLedger,
    slide_build_linkage: SlideBuildLinkage,
    item: RemediationExecutionItem,
) -> tuple[SlideLedger, SlideBuildLinkage]:
    stage_status = _status_for_execution(item.execution_status)
    updated_entries: list[SlideLedgerEntry] = []
    for entry in slide_ledger.entries:
        in_scope = False
        if item.slide_number is not None:
            in_scope = entry.slide_number == item.slide_number
        elif item.slide_range is not None:
            in_scope = item.slide_range.start <= entry.slide_number <= item.slide_range.end
        if not in_scope:
            updated_entries.append(entry)
            continue
        updated_entries.append(
            entry.model_copy(
                update={
                    "remediation_status": stage_status,
                    "remediation_finding_ids": _dedupe(list(entry.remediation_finding_ids) + [item.finding_id]),
                    "remediation_batch_ids": _dedupe(list(entry.remediation_batch_ids) + ([item.target_batch_id] if item.target_batch_id else [])),
                    "change_note": _dedupe([entry.change_note or "", item.action_taken])[-1],
                }
            )
        )

    updated_links = []
    for link in slide_build_linkage.slides:
        in_scope = False
        if item.slide_number is not None:
            in_scope = link.slide_number == item.slide_number
        elif item.slide_range is not None:
            in_scope = item.slide_range.start <= link.slide_number <= item.slide_range.end
        if not in_scope:
            updated_links.append(link)
            continue
        updated_links.append(
            link.model_copy(
                update={
                    "remediation_status": stage_status,
                    "remediation_finding_ids": _dedupe(list(link.remediation_finding_ids) + [item.finding_id]),
                    "remediation_batch_ids": _dedupe(list(link.remediation_batch_ids) + ([item.target_batch_id] if item.target_batch_id else [])),
                    "continuation_notes": _dedupe(list(link.continuation_notes) + [item.action_taken]),
                }
            )
        )
    return (
        slide_ledger.model_copy(update={"entries": updated_entries}),
        slide_build_linkage.model_copy(update={"slides": updated_links}),
    )


def _promote_existing_asset_for_action(
    asset_manifest: AssetManifest,
    action: RemediationAction,
    artifact_root: Path,
) -> tuple[AssetManifest, str]:
    matched = _match_action_assets(asset_manifest, action)
    alternate = next(
        (
            asset
            for asset in matched
            if asset.asset_kind in {AssetKind.DOCUMENT_CROP, AssetKind.IMAGE}
            and _resolve_path(asset.local_path, artifact_root) is not None
            and _resolve_path(asset.local_path, artifact_root).is_file()
        ),
        None,
    )
    if alternate is None:
        raise ValueError("no compile-ready alternate source asset is available for fallback promotion")

    updated_assets: list[AssetRecord] = []
    for asset in asset_manifest.assets:
        if asset.asset_id == alternate.asset_id:
            updated_assets.append(
                asset.model_copy(
                    update={
                        "status": AssetStatus.READY,
                        "notes": _dedupe([asset.notes or "", f"Promoted during bounded remediation from {action.finding_id}."])[-1],
                    }
                )
            )
            continue
        if asset in matched and asset.asset_kind in {AssetKind.DOCUMENT_CROP, AssetKind.IMAGE}:
            resolved = _resolve_path(asset.local_path, artifact_root)
            if resolved is None or not resolved.is_file():
                updated_assets.append(
                    asset.model_copy(
                        update={
                            "status": AssetStatus.REJECTED,
                            "limitations": _dedupe(list(asset.limitations) + [f"Deferred in favor of alternate asset during remediation {action.finding_id}."]),
                        }
                    )
                )
                continue
        updated_assets.append(asset)

    promoted_id = alternate.asset_id
    updated_assets.sort(
        key=lambda asset: (
            0 if asset.asset_id == promoted_id else 1 if asset in matched else 2,
            asset.slide_number,
            asset.asset_id,
        )
    )
    return asset_manifest.model_copy(update={"assets": updated_assets}), alternate.asset_id


def _promote_simplified_visual_for_action(
    asset_manifest: AssetManifest,
    viz_manifest: VizManifest,
    action: RemediationAction,
) -> tuple[AssetManifest, VizManifest, str]:
    records = _match_action_viz(viz_manifest, action)
    if not records:
        raise ValueError("no structured visual record matches the remediation scope")
    record = records[0]
    if not record.output_path:
        raise ValueError("structured visual has no canonical output_path to promote")

    updated_assets: list[AssetRecord] = []
    target_asset_id: str | None = None
    for asset in asset_manifest.assets:
        if asset.slide_id == record.spec.slide_id and asset.asset_kind == AssetKind.STRUCTURED_VISUAL:
            target_asset_id = asset.asset_id
            updated_assets.append(
                asset.model_copy(
                    update={
                        "status": AssetStatus.READY,
                        "local_path": record.output_path,
                        "limitations": _dedupe(list(asset.limitations) + ["Canonical simplified structured visual promoted during remediation."]),
                        "notes": _dedupe([asset.notes or "", f"Structured visual fallback promoted for {action.finding_id}."])[-1],
                    }
                )
            )
        else:
            updated_assets.append(asset)
    if target_asset_id is None:
        raise ValueError("structured visual asset registry entry is missing for the remediation target")

    updated_records: list[VizRecord] = []
    for current in viz_manifest.visuals:
        if current.spec.spec_id == record.spec.spec_id:
            updated_records.append(
                current.model_copy(
                    update={
                        "notes": _dedupe([current.notes or "", f"Canonical output confirmed during remediation {action.finding_id}."])[-1],
                    }
                )
            )
        else:
            updated_records.append(current)
    return (
        asset_manifest.model_copy(update={"assets": updated_assets}),
        viz_manifest.model_copy(update={"visuals": updated_records}),
        target_asset_id,
    )


def _normalize_rerun_stages(stages: list[str]) -> list[str]:
    return [stage for stage in RERUN_STAGE_ORDER if stage in stages]


def _merge_reports(
    base_report: QAReport,
    rerun_report: QAReport | None,
    execution_items: list[RemediationExecutionItem],
    slide_ledger: SlideLedger,
    slide_build_linkage: SlideBuildLinkage,
) -> tuple[QAReport, SlideLedger, SlideBuildLinkage]:
    items_by_finding = {item.finding_id: item for item in execution_items}
    retained = []
    for finding in base_report.findings:
        item = items_by_finding.get(finding.finding_id)
        if item is None:
            retained.append(finding)
            continue
        status = _finding_status_for_item(item)
        if status == FindingStatus.RESOLVED:
            continue
        retained.append(finding.model_copy(update={"status": status}))

    merged_findings = list(rerun_report.findings) if rerun_report is not None else []
    seen_ids = {finding.finding_id for finding in merged_findings}
    for finding in retained:
        if finding.finding_id not in seen_ids:
            merged_findings.append(finding)
            seen_ids.add(finding.finding_id)

    source_report = rerun_report if rerun_report is not None else base_report
    merged_report = source_report.model_copy(update={"findings": merged_findings})
    return _rebuild_qa_report(merged_report, slide_ledger, slide_build_linkage)


def apply_bounded_remediation(
    remediation_plan: RemediationPlan,
    batch_manifest: BatchManifest,
    context_lock: ContextLock,
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
    *,
    workflow_plan: WorkflowPlan | None = None,
    handoff_packet: HandoffPacket | None = None,
    asset_requests: AssetRequests | None = None,
    viz_spec: VizSpecSet | None = None,
    notes_path: str | Path | None = None,
    artifact_root: str | Path | None = None,
    state_output_dir: str | Path | None = None,
    build_output_dir: str | Path | None = None,
    visual_output_dir: str | Path | None = None,
) -> RemediationExecutionOutputs:
    root = Path(artifact_root).resolve() if artifact_root is not None else Path.cwd().resolve()
    state_dir = Path(state_output_dir).resolve() if state_output_dir is not None else root
    build_dir = Path(build_output_dir).resolve() if build_output_dir is not None else state_dir
    visual_dir = Path(visual_output_dir).resolve() if visual_output_dir is not None else state_dir
    qa_governance_path = state_dir / DEFAULT_STATE_FILENAMES["qa_governance"]
    current_qa_governance = load_state_file(qa_governance_path) if qa_governance_path.is_file() else None
    if current_qa_governance is not None and current_qa_governance.schema_name != "qa_governance":
        raise TypeError(f"expected qa_governance, found {current_qa_governance.schema_name}")

    current_asset_manifest = _clone_model(asset_manifest)
    current_viz_manifest = _clone_model(viz_manifest)
    current_slide_ledger = _clone_model(slide_ledger)
    current_slide_build_linkage = _clone_model(slide_build_linkage)
    current_build_manifest = _clone_model(build_manifest)
    current_qa_report = _clone_model(qa_report)
    current_batch_manifest = _clone_model(batch_manifest)
    current_context_lock = _clone_model(context_lock)
    current_state_capsule = _clone_model(state_capsule)
    current_handoff_packet = _clone_model(handoff_packet) if handoff_packet is not None else None

    execution_items: list[RemediationExecutionItem] = []
    requested_reruns: list[str] = []
    warnings: list[str] = []

    for action in remediation_plan.actions:
        item_status = RemediationExecutionStatus.SKIPPED
        action_taken = "No change applied."
        item_warnings: list[str] = []
        updated_artifacts: list[str] = []
        item_rerun_candidates: list[str] = []

        if action.execution_action not in SAFE_AUTO_ACTIONS:
            item_status = RemediationExecutionStatus.BLOCKED
            action_taken = "Remediation action is outside the bounded auto-apply allowlist."
            item_warnings.append(f"Unsupported execution action: {action.execution_action.value}")
        elif action.scope != RemediationScope.LOCAL_CHANGE_ONLY and action.execution_action not in {
            RemediationExecutionAction.MARK_DEFERRED,
            RemediationExecutionAction.MARK_BLOCKED,
            RemediationExecutionAction.MARK_REQUIRES_UPSTREAM_CHANGE,
        }:
            item_status = RemediationExecutionStatus.DEFERRED
            action_taken = "Deferred because the finding scope exceeds the allowed local auto-remediation boundary."
            item_warnings.append("Only local-change-only remediation items are auto-applied in this phase.")
        else:
            try:
                if action.execution_action == RemediationExecutionAction.MARK_DEFERRED:
                    item_status = RemediationExecutionStatus.DEFERRED
                    action_taken = "Marked safe to defer for a later bounded batch."
                elif action.execution_action in {
                    RemediationExecutionAction.MARK_BLOCKED,
                    RemediationExecutionAction.MARK_REQUIRES_UPSTREAM_CHANGE,
                }:
                    item_status = RemediationExecutionStatus.BLOCKED
                    action_taken = "Marked for manual upstream change; no auto-remediation applied."
                elif action.execution_action == RemediationExecutionAction.SYNC_STATUS_ONLY:
                    item_status = RemediationExecutionStatus.APPLIED
                    action_taken = "Synchronized remediation control-state markers without mutating content or assets."
                    updated_artifacts.extend(["slide-ledger.json", "slide-build-linkage.json"])
                    item_rerun_candidates = list(action.rerun_stages)
                    requested_reruns.extend(item_rerun_candidates)
                elif action.execution_action in {
                    RemediationExecutionAction.APPLY_KNOWN_FALLBACK,
                    RemediationExecutionAction.PROMOTE_EXISTING_ALTERNATE_ASSET,
                }:
                    current_asset_manifest, promoted_asset_id = _promote_existing_asset_for_action(current_asset_manifest, action, root)
                    item_status = RemediationExecutionStatus.APPLIED
                    action_taken = f"Promoted compile-ready source asset `{promoted_asset_id}` as the bounded fallback."
                    updated_artifacts.extend(["asset-manifest.json"])
                    item_rerun_candidates = list(action.rerun_stages or ["compile-pptx", "qa-deck", "orchestrate-large-deck"])
                    requested_reruns.extend(item_rerun_candidates)
                elif action.execution_action in {
                    RemediationExecutionAction.PROMOTE_SIMPLIFIED_STRUCTURED_VISUAL,
                    RemediationExecutionAction.DROP_BLOCKED_DENSE_VISUAL,
                }:
                    current_asset_manifest, current_viz_manifest, promoted_asset_id = _promote_simplified_visual_for_action(
                        current_asset_manifest,
                        current_viz_manifest,
                        action,
                    )
                    item_status = RemediationExecutionStatus.APPLIED
                    action_taken = f"Promoted the canonical structured visual asset `{promoted_asset_id}`."
                    updated_artifacts.extend(["asset-manifest.json", "viz-manifest.json"])
                    item_rerun_candidates = list(action.rerun_stages or ["compile-pptx", "qa-deck", "orchestrate-large-deck"])
                    requested_reruns.extend(item_rerun_candidates)
                elif action.execution_action == RemediationExecutionAction.RERUN_COMPILER:
                    item_status = RemediationExecutionStatus.APPLIED
                    action_taken = "Scheduled a bounded compiler refresh without mutating upstream content."
                    item_rerun_candidates = list(action.rerun_stages or ["compile-pptx", "qa-deck", "orchestrate-large-deck"])
                    requested_reruns.extend(item_rerun_candidates)
                elif action.execution_action == RemediationExecutionAction.RERUN_QA:
                    item_status = RemediationExecutionStatus.APPLIED
                    action_taken = "Scheduled a bounded QA refresh against the current compiled state."
                    item_rerun_candidates = list(action.rerun_stages or ["qa-deck", "orchestrate-large-deck"])
                    requested_reruns.extend(item_rerun_candidates)
                else:
                    item_status = RemediationExecutionStatus.BLOCKED
                    action_taken = "The requested remediation action is not safely executable from the current state package."
                    item_warnings.append(f"Blocked execution action: {action.execution_action.value}")
            except Exception as exc:
                item_status = RemediationExecutionStatus.FAILED
                action_taken = "Bounded remediation failed before downstream refresh."
                item_warnings.append(str(exc))

        item = RemediationExecutionItem(
            action_id=action.action_id,
            finding_id=action.finding_id,
            scope=action.scope,
            owner=action.owner,
            requested_action=action.execution_action,
            execution_status=item_status,
            action_taken=action_taken,
            downstream_stages_rerun=item_rerun_candidates,
            updated_artifacts=_dedupe(updated_artifacts),
            warnings=item_warnings,
            slide_number=action.slide_number,
            slide_range=action.slide_range,
            target_batch_id=action.target_batch_id,
        )
        current_slide_ledger, current_slide_build_linkage = _sync_remediation_metadata(current_slide_ledger, current_slide_build_linkage, item)
        execution_items.append(item)

    rerun_stages = _normalize_rerun_stages(_dedupe(requested_reruns))
    if "render-visuals" in rerun_stages:
        if viz_spec is None:
            warnings.append("Requested render-visuals refresh but viz_spec was not available; skipped.")
            rerun_stages = [stage for stage in rerun_stages if stage != "render-visuals"]
        else:
            visual_outputs = run_structured_visuals(
                viz_spec=viz_spec,
                design_system=design_system,
                deck_constitution=deck_constitution,
                layout_library=layout_library,
                slide_ledger=current_slide_ledger,
                output_dir=visual_dir,
                asset_requests=asset_requests,
                asset_manifest=current_asset_manifest,
                viz_manifest=current_viz_manifest,
                root=root,
            )
            current_viz_manifest = visual_outputs.viz_manifest
            current_asset_manifest = visual_outputs.asset_manifest
            current_slide_ledger = visual_outputs.slide_ledger

    pptx_path: Path | None = None
    if "compile-pptx" in rerun_stages:
        compile_outputs = compile_pptx(
            blueprint=blueprint,
            design_system=design_system,
            deck_constitution=deck_constitution,
            layout_library=layout_library,
            slide_ledger=current_slide_ledger,
            asset_manifest=current_asset_manifest,
            viz_manifest=current_viz_manifest,
            output_dir=build_dir,
            batch_manifest=current_batch_manifest,
            state_capsule=current_state_capsule,
            notes_path=notes_path,
            pptx_name=Path(current_build_manifest.pptx_path).name if current_build_manifest.pptx_path else "deck.pptx",
            root=root,
        )
        current_build_manifest = compile_outputs.build_manifest
        current_slide_build_linkage = compile_outputs.slide_build_linkage
        current_slide_ledger = compile_outputs.slide_ledger
        current_batch_manifest = compile_outputs.batch_manifest or current_batch_manifest
        current_state_capsule = compile_outputs.state_capsule or current_state_capsule
        pptx_path = compile_outputs.pptx_path

    rerun_qa_report: QAReport | None = None
    if "qa-deck" in rerun_stages:
        qa_outputs = run_deck_qa(
            blueprint=blueprint,
            design_system=design_system,
            deck_constitution=deck_constitution,
            layout_library=layout_library,
            slide_ledger=current_slide_ledger,
            asset_manifest=current_asset_manifest,
            viz_manifest=current_viz_manifest,
            build_manifest=current_build_manifest,
            slide_build_linkage=current_slide_build_linkage,
            state_capsule=current_state_capsule,
            prior_report=current_qa_report,
            qa_governance=current_qa_governance,
            artifact_root=root,
        )
        rerun_qa_report = qa_outputs.qa_report
        current_qa_governance = qa_outputs.qa_governance or current_qa_governance
        current_slide_ledger = qa_outputs.slide_ledger
        current_slide_build_linkage = qa_outputs.slide_build_linkage
        current_state_capsule = qa_outputs.state_capsule or current_state_capsule

    current_qa_report, current_slide_ledger, current_slide_build_linkage = _merge_reports(
        current_qa_report,
        rerun_qa_report,
        execution_items,
        current_slide_ledger,
        current_slide_build_linkage,
    )

    remaining_plan = _remaining_plan(remediation_plan, execution_items, current_qa_report)
    current_context_lock = _update_context_lock(current_context_lock, current_qa_report)

    report_pointer = f"{_canonical_state_root(current_state_capsule, state_dir, root)}/{DEFAULT_STATE_FILENAMES['remediation_execution_report']}"
    current_state_capsule = _update_state_capsule(
        current_state_capsule,
        current_qa_report,
        remaining_plan,
        execution_report_path=report_pointer,
    )
    if current_handoff_packet is not None:
        current_handoff_packet = _update_handoff_packet(
            current_handoff_packet,
            current_qa_report,
            remaining_plan,
            execution_report_name=DEFAULT_STATE_FILENAMES["remediation_execution_report"],
        )

    if workflow_plan is not None and execution_items:
        orchestration_outputs = orchestrate_large_deck(
            workflow_plan=workflow_plan,
            blueprint=blueprint,
            design_system=design_system,
            deck_constitution=deck_constitution,
            layout_library=layout_library,
            slide_ledger=current_slide_ledger,
            build_manifest=current_build_manifest,
            slide_build_linkage=current_slide_build_linkage,
            qa_report=current_qa_report,
            pointer_root=_canonical_state_root(current_state_capsule, state_dir, root),
            canonical_state_root=_canonical_state_root(current_state_capsule, state_dir, root),
        )
        current_batch_manifest = orchestration_outputs.batch_manifest
        current_context_lock = _update_context_lock(orchestration_outputs.context_lock, current_qa_report)
        current_handoff_packet = orchestration_outputs.handoff_packet
        current_state_capsule = _update_state_capsule(
            orchestration_outputs.state_capsule,
            current_qa_report,
            orchestration_outputs.remediation_plan,
            execution_report_path=report_pointer,
        )
        remaining_plan = orchestration_outputs.remediation_plan
        current_slide_ledger = orchestration_outputs.slide_ledger
        if orchestration_outputs.slide_build_linkage is not None:
            current_slide_build_linkage = orchestration_outputs.slide_build_linkage
        if current_handoff_packet is not None:
            current_handoff_packet = _update_handoff_packet(
                current_handoff_packet,
                current_qa_report,
                remaining_plan,
                execution_report_name=DEFAULT_STATE_FILENAMES["remediation_execution_report"],
            )

    execution_items = [
        item.model_copy(
            update={
                "downstream_stages_rerun": [
                    stage for stage in rerun_stages if stage in set(item.downstream_stages_rerun)
                ]
            }
        )
        for item in execution_items
    ]

    updated_artifacts = [DEFAULT_STATE_FILENAMES["remediation_execution_report"]]
    if execution_items:
        updated_artifacts.extend(["slide-ledger.json", "qa-report.json", "asset-manifest.json", "viz-manifest.json"])
        if "compile-pptx" in rerun_stages:
            updated_artifacts.extend(["build-manifest.json", "slide-build-linkage.json"])
        if workflow_plan is not None:
            updated_artifacts.extend(["batch-manifest.json", "context-lock.json", "state-capsule.json", "remediation-plan.json"])
            if current_handoff_packet is not None:
                updated_artifacts.append("handoff-packet.json")
    updated_artifacts = _dedupe(updated_artifacts)
    summary = RemediationExecutionSummary(
        total_items=len(execution_items),
        applied_count=sum(1 for item in execution_items if item.execution_status == RemediationExecutionStatus.APPLIED),
        deferred_count=sum(1 for item in execution_items if item.execution_status == RemediationExecutionStatus.DEFERRED),
        blocked_count=sum(1 for item in execution_items if item.execution_status == RemediationExecutionStatus.BLOCKED),
        failed_count=sum(1 for item in execution_items if item.execution_status == RemediationExecutionStatus.FAILED),
        skipped_count=sum(1 for item in execution_items if item.execution_status == RemediationExecutionStatus.SKIPPED),
        rerun_stage_counts=dict(Counter(rerun_stages)),
    )
    report = RemediationExecutionReport(
        report_id=f"remediation-execution-{remediation_plan.deck_title.lower().replace(' ', '-')}",
        deck_title=remediation_plan.deck_title,
        source_plan_id=remediation_plan.plan_id,
        source_report_id=remediation_plan.generated_from_report_id,
        summary=summary,
        items=execution_items,
        rerun_stages=rerun_stages,
        updated_artifacts=updated_artifacts,
        warnings=warnings,
        remaining_plan_id=remaining_plan.plan_id,
        remaining_actionable_count=len(remaining_plan.actions),
        remaining_blocking_finding_ids=list(remaining_plan.blocking_finding_ids),
        ship_blocked_after_execution=remaining_plan.ship_blocked,
        canonical_state_root=_canonical_state_root(current_state_capsule, state_dir, root),
    )
    return RemediationExecutionOutputs(
        remediation_execution_report=report,
        asset_manifest=current_asset_manifest,
        viz_manifest=current_viz_manifest,
        build_manifest=current_build_manifest,
        qa_report=current_qa_report,
        qa_governance=current_qa_governance,
        slide_ledger=current_slide_ledger,
        slide_build_linkage=current_slide_build_linkage,
        batch_manifest=current_batch_manifest,
        context_lock=current_context_lock,
        handoff_packet=current_handoff_packet,
        state_capsule=current_state_capsule,
        remediation_plan=remaining_plan,
        pptx_path=pptx_path,
    )


def _load_optional_state(path: str | Path | None, expected_schema: str):
    if path is None:
        return None
    candidate = Path(path)
    if not candidate.is_file():
        return None
    model = load_state_file(candidate)
    if model.schema_name != expected_schema:
        raise TypeError(f"expected {expected_schema}, found {model.schema_name}")
    return model


def _resolve_optional_input(
    explicit_path: str | Path | None,
    *,
    schema_name: str,
    state_capsule: StateCapsule,
    search_root: Path,
    artifact_root: Path,
):
    if explicit_path is not None:
        return _load_optional_state(explicit_path, schema_name)
    for pointer in state_capsule.file_pointers:
        if pointer.schema_name != schema_name:
            continue
        resolved = _resolve_path(pointer.path, artifact_root)
        if resolved is not None and resolved.is_file():
            return _load_optional_state(resolved, schema_name)
    fallback = search_root / DEFAULT_STATE_FILENAMES[schema_name]
    if fallback.is_file():
        return _load_optional_state(fallback, schema_name)
    return None


def apply_bounded_remediation_from_files(
    remediation_plan_path: str | Path,
    batch_manifest_path: str | Path,
    context_lock_path: str | Path,
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
    workflow_plan_path: str | Path | None = None,
    handoff_packet_path: str | Path | None = None,
    asset_requests_path: str | Path | None = None,
    viz_spec_path: str | Path | None = None,
    notes_path: str | Path | None = None,
    artifact_root: str | Path | None = None,
    state_output_dir: str | Path | None = None,
    build_output_dir: str | Path | None = None,
    visual_output_dir: str | Path | None = None,
) -> RemediationExecutionOutputs:
    remediation_plan = load_state_file(remediation_plan_path)
    batch_manifest = load_state_file(batch_manifest_path)
    context_lock = load_state_file(context_lock_path)
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

    if remediation_plan.schema_name != "remediation_plan":
        raise TypeError(f"expected remediation_plan, found {remediation_plan.schema_name}")
    if batch_manifest.schema_name != "batch_manifest":
        raise TypeError(f"expected batch_manifest, found {batch_manifest.schema_name}")
    if context_lock.schema_name != "context_lock":
        raise TypeError(f"expected context_lock, found {context_lock.schema_name}")
    if state_capsule.schema_name != "state_capsule":
        raise TypeError(f"expected state_capsule, found {state_capsule.schema_name}")
    if slide_ledger.schema_name != "slide_ledger":
        raise TypeError(f"expected slide_ledger, found {slide_ledger.schema_name}")
    if qa_report.schema_name != "qa_report":
        raise TypeError(f"expected qa_report, found {qa_report.schema_name}")
    if blueprint.schema_name != "blueprint":
        raise TypeError(f"expected blueprint, found {blueprint.schema_name}")
    if design_system.schema_name != "design_system":
        raise TypeError(f"expected design_system, found {design_system.schema_name}")
    if deck_constitution.schema_name != "deck_constitution":
        raise TypeError(f"expected deck_constitution, found {deck_constitution.schema_name}")
    if layout_library.schema_name != "layout_library":
        raise TypeError(f"expected layout_library, found {layout_library.schema_name}")
    if asset_manifest.schema_name != "asset_manifest":
        raise TypeError(f"expected asset_manifest, found {asset_manifest.schema_name}")
    if viz_manifest.schema_name != "viz_manifest":
        raise TypeError(f"expected viz_manifest, found {viz_manifest.schema_name}")
    if build_manifest.schema_name != "build_manifest":
        raise TypeError(f"expected build_manifest, found {build_manifest.schema_name}")
    if slide_build_linkage.schema_name != "slide_build_linkage":
        raise TypeError(f"expected slide_build_linkage, found {slide_build_linkage.schema_name}")

    artifact_root_path = Path(artifact_root).resolve() if artifact_root is not None else Path.cwd().resolve()
    search_root = Path(state_output_dir).resolve() if state_output_dir is not None else Path(state_capsule_path).resolve().parent
    workflow_plan = _resolve_optional_input(
        workflow_plan_path,
        schema_name="workflow_plan",
        state_capsule=state_capsule,
        search_root=search_root,
        artifact_root=artifact_root_path,
    )
    handoff_packet = _resolve_optional_input(
        handoff_packet_path,
        schema_name="handoff_packet",
        state_capsule=state_capsule,
        search_root=search_root,
        artifact_root=artifact_root_path,
    )
    asset_requests = _resolve_optional_input(
        asset_requests_path,
        schema_name="asset_requests",
        state_capsule=state_capsule,
        search_root=search_root,
        artifact_root=artifact_root_path,
    )
    viz_spec = _resolve_optional_input(
        viz_spec_path,
        schema_name="viz_spec",
        state_capsule=state_capsule,
        search_root=search_root,
        artifact_root=artifact_root_path,
    )

    return apply_bounded_remediation(
        remediation_plan=remediation_plan,
        batch_manifest=batch_manifest,
        context_lock=context_lock,
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
        workflow_plan=workflow_plan,
        handoff_packet=handoff_packet,
        asset_requests=asset_requests,
        viz_spec=viz_spec,
        notes_path=notes_path,
        artifact_root=artifact_root_path,
        state_output_dir=state_output_dir,
        build_output_dir=build_output_dir,
        visual_output_dir=visual_output_dir,
    )


def write_remediation_execution_outputs(
    outputs: RemediationExecutionOutputs,
    state_output_dir: str | Path,
    *,
    build_output_dir: str | Path | None = None,
) -> dict[str, Path]:
    state_root = Path(state_output_dir)
    state_root.mkdir(parents=True, exist_ok=True)
    build_root = Path(build_output_dir) if build_output_dir is not None else state_root
    build_root.mkdir(parents=True, exist_ok=True)
    written = {
        "remediation_execution_report": save_state_file(
            outputs.remediation_execution_report,
            state_root / DEFAULT_STATE_FILENAMES["remediation_execution_report"],
        ),
        "asset_manifest": save_state_file(outputs.asset_manifest, state_root / DEFAULT_STATE_FILENAMES["asset_manifest"]),
        "viz_manifest": save_state_file(outputs.viz_manifest, state_root / DEFAULT_STATE_FILENAMES["viz_manifest"]),
        "qa_report": save_state_file(outputs.qa_report, state_root / DEFAULT_STATE_FILENAMES["qa_report"]),
        "slide_ledger": save_state_file(outputs.slide_ledger, state_root / DEFAULT_STATE_FILENAMES["slide_ledger"]),
        "batch_manifest": save_state_file(outputs.batch_manifest, state_root / DEFAULT_STATE_FILENAMES["batch_manifest"]),
        "context_lock": save_state_file(outputs.context_lock, state_root / DEFAULT_STATE_FILENAMES["context_lock"]),
        "state_capsule": save_state_file(outputs.state_capsule, state_root / DEFAULT_STATE_FILENAMES["state_capsule"]),
        "remediation_plan": save_state_file(outputs.remediation_plan, state_root / DEFAULT_STATE_FILENAMES["remediation_plan"]),
        "build_manifest": save_state_file(outputs.build_manifest, build_root / "build-manifest.json"),
        "slide_build_linkage": save_state_file(outputs.slide_build_linkage, build_root / "slide-build-linkage.json"),
    }
    if outputs.qa_governance is not None:
        written["qa_governance"] = save_state_file(
            outputs.qa_governance,
            state_root / DEFAULT_STATE_FILENAMES["qa_governance"],
        )
    if outputs.handoff_packet is not None:
        written["handoff_packet"] = save_state_file(outputs.handoff_packet, state_root / DEFAULT_STATE_FILENAMES["handoff_packet"])
    if outputs.pptx_path is not None:
        written["pptx"] = outputs.pptx_path
    return written


