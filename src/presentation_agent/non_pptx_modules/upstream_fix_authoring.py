"""Deterministic Phase 13 upstream-fix authoring over unresolved remediation backlog."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from ..pptx_compiler import BuildManifest, SlideBuildLinkage, load_pptx_compile_file
from ..compat.legacy_non_pptx import (
    ApprovalPacket,
    ApprovalPacketSet,
    ArtifactImpactSummary,
    AssetManifest,
    AssetRecord,
    AssetRequests,
    AuthoringDeltaRecord,
    AuthoringDeltas,
    BatchManifest,
    Blueprint,
    BlueprintSlide,
    BlockedManualUpstreamIssue,
    ContextLock,
    ContractModel,
    DEFAULT_STATE_FILENAMES,
    DeckConstitution,
    DeltaOperation,
    DeltaOption,
    DesignSystem,
    FixRiskLevel,
    HandoffPacket,
    LayoutLibrary,
    LayoutPattern,
    PacketApprovalMode,
    QAFinding,
    QAReport,
    RemediationAction,
    RemediationDisposition,
    RemediationExecutionReport,
    RemediationExecutionStatus,
    RemediationExecutionAction,
    RemediationOwner,
    RemediationPlan,
    RemediationScope,
    SlideLedger,
    SlideLedgerEntry,
    SlideRange,
    StateCapsule,
    StateFilePointer,
    UpstreamArtifactName,
    UpstreamFixPlan,
    UpstreamFixProposal,
    VisualType,
    VizManifest,
    VizRecord,
    VizSpec,
    VizSpecSet,
    load_state_file,
    save_state_file,
)


PIPELINE_RERUN_ORDER = [
    "derive-assets",
    "extract-assets",
    "review-crops",
    "render-visuals",
    "compile-pptx",
    "qa-deck",
    "orchestrate-large-deck",
    "apply-remediation",
]

TERM_RE = re.compile(r'"([^"]+)"')
PUNCTUATION_ENDINGS = (".", "!", "?", ":", ";")


class UpstreamFixAuthoringOutputs(ContractModel):
    upstream_fix_plan: UpstreamFixPlan
    approval_packet: ApprovalPacketSet
    authoring_deltas: AuthoringDeltas
    state_capsule: StateCapsule
    handoff_packet: HandoffPacket


class _DeltaBuilder:
    def __init__(self) -> None:
        self._deltas: list[AuthoringDeltaRecord] = []
        self._next_index = 1

    def add(
        self,
        *,
        fix_id: str,
        target_artifact: UpstreamArtifactName,
        selector: str,
        field_path: str,
        operation: DeltaOperation,
        current_value,
        rationale: str,
        proposed_value=None,
        options: list[DeltaOption] | None = None,
    ) -> str:
        delta_id = f"delta-{self._next_index:03d}"
        self._next_index += 1
        self._deltas.append(
            AuthoringDeltaRecord(
                delta_id=delta_id,
                fix_id=fix_id,
                target_artifact=target_artifact,
                selector=selector,
                field_path=field_path,
                operation=operation,
                current_value=current_value,
                proposed_value=proposed_value,
                options=options or [],
                rationale=rationale,
            )
        )
        return delta_id

    @property
    def deltas(self) -> list[AuthoringDeltaRecord]:
        return list(self._deltas)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def _slug(text: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in text.lower()).strip("-") or "item"


def _range_for_action(action: RemediationAction) -> SlideRange:
    if action.slide_range is not None:
        return action.slide_range
    if action.slide_number is not None:
        return SlideRange(start=action.slide_number, end=action.slide_number)
    raise ValueError(f"remediation action {action.action_id} is missing slide context")


def _entries_in_range(slide_ledger: SlideLedger, slide_range: SlideRange) -> list[SlideLedgerEntry]:
    return [
        entry
        for entry in slide_ledger.entries
        if slide_range.start <= entry.slide_number <= slide_range.end
    ]


def _request_for_action(asset_requests: AssetRequests | None, action: RemediationAction):
    if asset_requests is None:
        return None
    for request in asset_requests.requests:
        if action.slide_id is not None and request.slide_id == action.slide_id:
            return request
        if action.slide_number is not None and request.slide_number == action.slide_number:
            return request
    return None


def _spec_for_action(viz_spec: VizSpecSet | None, action: RemediationAction) -> VizSpec | None:
    if viz_spec is None:
        return None
    for spec in viz_spec.specs:
        if action.slide_id is not None and spec.slide_id == action.slide_id:
            return spec
        if action.slide_number is not None and spec.slide_number == action.slide_number:
            return spec
    return None


def _asset_records_for_action(asset_manifest: AssetManifest, action: RemediationAction) -> list[AssetRecord]:
    slide_range = _range_for_action(action)
    return [
        asset
        for asset in asset_manifest.assets
        if slide_range.start <= asset.slide_number <= slide_range.end
    ]


def _viz_records_for_action(viz_manifest: VizManifest, action: RemediationAction) -> list[VizRecord]:
    slide_range = _range_for_action(action)
    return [
        record
        for record in viz_manifest.visuals
        if slide_range.start <= record.spec.slide_number <= slide_range.end
    ]


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _clean_title_candidate(value: str) -> str:
    text = _normalize_text(value).strip()
    while text.endswith(PUNCTUATION_ENDINGS):
        text = text[:-1].rstrip()
    if len(text) > 72:
        text = text[:69].rstrip(" ,;:-") + "..."
    return text


def _title_options(slide: BlueprintSlide | None, entry: SlideLedgerEntry) -> list[str]:
    candidates = [
        _clean_title_candidate(entry.one_line_takeaway),
        _clean_title_candidate(entry.main_message),
        _clean_title_candidate(entry.title),
    ]
    if slide is not None:
        candidates.extend(
            [
                _clean_title_candidate(slide.one_line_takeaway),
                _clean_title_candidate(slide.main_message),
                _clean_title_candidate(slide.title),
            ]
        )
    return [candidate for candidate in _dedupe(candidates) if candidate and candidate != entry.title]


def _term_pairs(deck_constitution: DeckConstitution) -> list[tuple[str, list[str]]]:
    pairs: list[tuple[str, list[str]]] = []
    for rule in deck_constitution.terminology_rules:
        terms = [_normalize_text(term).lower() for term in TERM_RE.findall(rule)]
        if len(terms) >= 2:
            pairs.append((terms[0], terms[1:]))
    return pairs


def _replace_discouraged_terms(text: str, preferred: str, discouraged: list[str]) -> str:
    updated = text
    for term in discouraged:
        if not term:
            continue
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        updated = pattern.sub(preferred, updated)
    return _normalize_text(updated)


def _term_replacements(
    text: str,
    deck_constitution: DeckConstitution,
) -> tuple[str | None, str | None]:
    lowered = text.lower()
    for preferred, discouraged_terms in _term_pairs(deck_constitution):
        used = [term for term in discouraged_terms if term in lowered]
        if used and preferred not in lowered:
            updated = _replace_discouraged_terms(text, preferred, used)
            if updated != text:
                return updated, preferred
    return None, None


def _compatible_patterns(
    layout_library: LayoutLibrary,
    *,
    visual_type: VisualType,
    current_pattern_id: str,
) -> list[LayoutPattern]:
    patterns = [
        pattern
        for pattern in layout_library.patterns
        if pattern.pattern_id != current_pattern_id and visual_type in pattern.supported_visual_types
    ]
    return sorted(patterns, key=lambda pattern: pattern.pattern_id)


def _ordered_reruns(stages: list[str]) -> list[str]:
    stage_set = set(stages)
    return [stage for stage in PIPELINE_RERUN_ORDER if stage in stage_set]


def _artifact_family_name(artifacts: list[UpstreamArtifactName]) -> str:
    artifact_set = set(artifacts)
    if artifact_set & {UpstreamArtifactName.ASSET_REQUESTS}:
        return "asset"
    if artifact_set & {UpstreamArtifactName.VIZ_SPEC}:
        return "visual"
    if artifact_set & {UpstreamArtifactName.DESIGN_SYSTEM, UpstreamArtifactName.LAYOUT_LIBRARY}:
        return "design"
    if artifact_set & {UpstreamArtifactName.DECK_CONSTITUTION}:
        return "constitution"
    return "content"


def _approval_requirement(artifacts: list[UpstreamArtifactName]) -> str:
    artifact_set = set(artifacts)
    if artifact_set & {UpstreamArtifactName.DESIGN_SYSTEM, UpstreamArtifactName.LAYOUT_LIBRARY}:
        return "design-review-change-request"
    if artifact_set & {UpstreamArtifactName.ASSET_REQUESTS, UpstreamArtifactName.VIZ_SPEC} and not artifact_set & {
        UpstreamArtifactName.BLUEPRINT,
        UpstreamArtifactName.DECK_CONSTITUTION,
        UpstreamArtifactName.DESIGN_SYSTEM,
        UpstreamArtifactName.LAYOUT_LIBRARY,
        UpstreamArtifactName.SLIDE_LEDGER,
    }:
        return "production-handoff-change-request"
    return "gate-2-change-request"


def _required_approvals(artifacts: list[UpstreamArtifactName]) -> list[str]:
    approvals: list[str] = ["Deck owner"]
    artifact_set = set(artifacts)
    if artifact_set & {UpstreamArtifactName.DESIGN_SYSTEM, UpstreamArtifactName.LAYOUT_LIBRARY}:
        approvals.append("Design approver")
    if artifact_set & {UpstreamArtifactName.ASSET_REQUESTS, UpstreamArtifactName.VIZ_SPEC}:
        approvals.append("Production owner")
    return _dedupe(approvals)


def _risk_level(scope: RemediationScope, artifacts: list[UpstreamArtifactName]) -> FixRiskLevel:
    artifact_set = set(artifacts)
    if scope == RemediationScope.DECK_LEVEL_REFLOW or artifact_set & {UpstreamArtifactName.DESIGN_SYSTEM}:
        return FixRiskLevel.HIGH
    if scope == RemediationScope.SECTION_LEVEL_REFLOW or artifact_set & {
        UpstreamArtifactName.LAYOUT_LIBRARY,
        UpstreamArtifactName.DECK_CONSTITUTION,
    }:
        return FixRiskLevel.MEDIUM
    return FixRiskLevel.LOW


def _stages_for_artifacts(
    artifacts: list[UpstreamArtifactName],
    *,
    asset_request=None,
    viz_spec: VizSpec | None = None,
) -> list[str]:
    stages: list[str] = []
    artifact_set = set(artifacts)
    if artifact_set & {
        UpstreamArtifactName.BLUEPRINT,
        UpstreamArtifactName.SLIDE_LEDGER,
        UpstreamArtifactName.DECK_CONSTITUTION,
    }:
        stages.extend(["compile-pptx", "qa-deck", "orchestrate-large-deck"])
    if UpstreamArtifactName.DESIGN_SYSTEM in artifact_set:
        stages.extend(["render-visuals", "compile-pptx", "qa-deck", "orchestrate-large-deck"])
    if UpstreamArtifactName.LAYOUT_LIBRARY in artifact_set:
        stages.extend(["compile-pptx", "qa-deck", "orchestrate-large-deck"])
    if UpstreamArtifactName.ASSET_REQUESTS in artifact_set:
        if asset_request is not None and getattr(asset_request, "asset_kind", None) is not None and asset_request.asset_kind.value == "structured-visual":
            stages.extend(["render-visuals", "compile-pptx", "qa-deck", "orchestrate-large-deck"])
        else:
            stages.extend(["extract-assets", "review-crops", "compile-pptx", "qa-deck", "orchestrate-large-deck"])
    if UpstreamArtifactName.VIZ_SPEC in artifact_set or viz_spec is not None:
        stages.extend(["render-visuals", "compile-pptx", "qa-deck", "orchestrate-large-deck"])
    return _ordered_reruns(stages)


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


def _packet_objective(scope: RemediationScope, artifacts: list[UpstreamArtifactName], slide_range: SlideRange) -> str:
    label = slide_range.label()
    family = _artifact_family_name(artifacts)
    if scope == RemediationScope.LOCAL_CHANGE_ONLY:
        return f"Approve the bounded {family} change for slide {label}."
    if scope == RemediationScope.SECTION_LEVEL_REFLOW:
        return f"Approve the coordinated {family} change across slides {label}."
    return f"Review the deck-level {family} change for slides {label}."


def _update_state_capsule(
    state_capsule: StateCapsule,
    *,
    pointer_root: str,
    packet_ids: list[str],
    fix_ids: list[str],
    blocked_items: list[BlockedManualUpstreamIssue],
) -> StateCapsule:
    file_pointers = list(state_capsule.file_pointers)
    for schema_name in ("upstream_fix_plan", "approval_packet", "authoring_deltas"):
        file_pointers = _upsert_pointer(
            file_pointers,
            schema_name=schema_name,
            path=f"{pointer_root}/{DEFAULT_STATE_FILENAMES[schema_name]}",
        )
    open_issues = _dedupe(
        list(state_capsule.open_issues)
        + [f"Approval packet {packet_id} is waiting for review." for packet_id in packet_ids]
        + [item.summary for item in blocked_items]
    )
    pending_actions = _dedupe(
        [f"Review approval packet {packet_id} before rerunning downstream stages." for packet_id in packet_ids]
        + [item.suggested_manual_next_step for item in blocked_items]
    )
    if not pending_actions:
        pending_actions = list(state_capsule.pending_actions) or ["No upstream approval packets are pending."]
    return state_capsule.model_copy(
        update={
            "file_pointers": file_pointers,
            "open_issues": open_issues,
            "pending_actions": pending_actions,
            "pending_approval_packet_ids": list(packet_ids),
            "pending_upstream_fix_ids": list(fix_ids),
            "updated_at": datetime.now(UTC),
        }
    )


def _update_handoff_packet(
    handoff_packet: HandoffPacket,
    *,
    packet_ids: list[str],
    fix_ids: list[str],
    blocked_items: list[BlockedManualUpstreamIssue],
) -> HandoffPacket:
    produced_artifacts = _dedupe(
        list(handoff_packet.produced_artifacts)
        + [
            DEFAULT_STATE_FILENAMES["upstream_fix_plan"],
            DEFAULT_STATE_FILENAMES["approval_packet"],
            DEFAULT_STATE_FILENAMES["authoring_deltas"],
        ]
    )
    open_issues = _dedupe(
        list(handoff_packet.open_issues)
        + [f"Approval packet {packet_id} is waiting for review." for packet_id in packet_ids]
        + [item.summary for item in blocked_items]
    )
    instructions = _dedupe(
        list(handoff_packet.handoff_instructions)
        + (
            ["Review the prepared approval packets before rerunning any upstream or downstream worker stage."]
            if packet_ids
            else []
        )
        + [item.suggested_manual_next_step for item in blocked_items]
    )
    verification_items = _dedupe(
        list(handoff_packet.verification_items_open)
        + [f"Approval packet {packet_id}" for packet_id in packet_ids]
        + [item.blocked_reason for item in blocked_items]
    )
    return handoff_packet.model_copy(
        update={
            "produced_artifacts": produced_artifacts,
            "open_issues": open_issues,
            "verification_items_open": verification_items,
            "pending_approval_packet_ids": list(packet_ids),
            "pending_upstream_fix_ids": list(fix_ids),
            "handoff_instructions": instructions,
            "generated_at": datetime.now(UTC),
        }
    )


def _default_skill_for_owner(owner: RemediationOwner) -> str:
    if owner == RemediationOwner.UPSTREAM_CONTENT_STORY:
        return "deck-orchestrator"
    if owner == RemediationOwner.CROP_SOURCE_ASSET:
        return "document-asset-crop"
    if owner == RemediationOwner.STRUCTURED_VISUAL:
        return "structured-visuals"
    if owner == RemediationOwner.COMPILER_LAYOUT:
        return "pptx-compiler"
    return "deck-qa"


def _location_from_finding(item, finding: QAFinding | None) -> tuple[int | None, SlideRange | None]:
    slide_number = item.slide_number if item.slide_number is not None else (finding.slide_number if finding is not None else None)
    slide_range = item.slide_range
    if slide_range is None and finding is not None and finding.slide_range is not None:
        slide_range = finding.slide_range
    if slide_range is None and slide_number is not None:
        slide_range = SlideRange(start=slide_number, end=slide_number)
    return slide_number, slide_range


def _synthetic_action_from_execution_item(
    item,
    finding: QAFinding | None,
) -> RemediationAction | None:
    if item.execution_status not in {
        RemediationExecutionStatus.DEFERRED,
        RemediationExecutionStatus.BLOCKED,
        RemediationExecutionStatus.FAILED,
    }:
        return None
    slide_number, slide_range = _location_from_finding(item, finding)
    if slide_number is None and slide_range is None:
        return None
    if item.execution_status == RemediationExecutionStatus.DEFERRED:
        disposition = RemediationDisposition.SAFE_TO_DEFER
        execution_action = RemediationExecutionAction.MARK_DEFERRED
    else:
        disposition = RemediationDisposition.BLOCK_SHIP if finding is not None and finding.blocking else RemediationDisposition.FIX_BATCH_REQUIRED
        execution_action = RemediationExecutionAction.MARK_REQUIRES_UPSTREAM_CHANGE
    rationale = finding.recommendation if finding is not None else item.action_taken
    return RemediationAction(
        action_id=item.action_id,
        finding_id=item.finding_id,
        severity=finding.severity if finding is not None else "major",
        qa_layer=finding.qa_layer if finding is not None else "deck",
        category=finding.category if finding is not None else "execution-backlog",
        scope=item.scope,
        owner=item.owner,
        disposition=disposition,
        target_skill=finding.remediation_skill if finding is not None else _default_skill_for_owner(item.owner),
        next_action=rationale,
        rationale=rationale,
        blocking=finding.blocking if finding is not None else item.execution_status != RemediationExecutionStatus.DEFERRED,
        execution_action=execution_action,
        rerun_stages=list(item.downstream_stages_rerun),
        slide_number=slide_number,
        slide_id=finding.slide_id if finding is not None else None,
        slide_range=slide_range,
        target_batch_id=item.target_batch_id,
        tags=["phase-13-synthesized-from-execution-report"],
    )


def _candidate_actions(
    remediation_plan: RemediationPlan,
    remediation_execution_report: RemediationExecutionReport,
    qa_report: QAReport,
) -> list[RemediationAction]:
    actions = list(remediation_plan.actions)
    actions_by_finding = {action.finding_id: action for action in actions}
    findings_by_id = {finding.finding_id: finding for finding in qa_report.findings}
    for item in remediation_execution_report.items:
        if item.finding_id in actions_by_finding:
            continue
        synthetic_action = _synthetic_action_from_execution_item(item, findings_by_id.get(item.finding_id))
        if synthetic_action is not None:
            actions.append(synthetic_action)
            actions_by_finding[synthetic_action.finding_id] = synthetic_action
    return actions


def _make_title_fix(
    action: RemediationAction,
    slide: BlueprintSlide | None,
    entry: SlideLedgerEntry,
    builder: _DeltaBuilder,
) -> tuple[UpstreamFixProposal, list[UpstreamArtifactName]] | None:
    title_options = _title_options(slide, entry)
    if not title_options:
        return None
    fix_id = f"fix-{action.finding_id}"
    option_models = [
        DeltaOption(
            option_id=f"{fix_id}-title-{index}",
            label=option,
            value=option,
            rationale="Use a shorter claim-led title for the approved slide.",
        )
        for index, option in enumerate(title_options, start=1)
    ]
    delta_ids = [
        builder.add(
            fix_id=fix_id,
            target_artifact=UpstreamArtifactName.BLUEPRINT,
            selector=f"slides[slide_number={entry.slide_number}]",
            field_path="title",
            operation=DeltaOperation.CHOOSE_ONE,
            current_value=slide.title if slide is not None else entry.title,
            options=option_models,
            rationale="Keep the approved blueprint title aligned to a faster one-line claim.",
        ),
        builder.add(
            fix_id=fix_id,
            target_artifact=UpstreamArtifactName.SLIDE_LEDGER,
            selector=f"entries[slide_number={entry.slide_number}]",
            field_path="title",
            operation=DeltaOperation.CHOOSE_ONE,
            current_value=entry.title,
            options=option_models,
            rationale="Keep the slide ledger synchronized with the approved title choice.",
        ),
    ]
    if entry.final_title is not None:
        delta_ids.append(
            builder.add(
                fix_id=fix_id,
                target_artifact=UpstreamArtifactName.SLIDE_LEDGER,
                selector=f"entries[slide_number={entry.slide_number}]",
                field_path="final_title",
                operation=DeltaOperation.CHOOSE_ONE,
                current_value=entry.final_title,
                options=option_models,
                rationale="Carry the same approved title choice into the final_title field.",
            )
        )
    artifacts = [UpstreamArtifactName.BLUEPRINT, UpstreamArtifactName.SLIDE_LEDGER]
    fix = UpstreamFixProposal(
        fix_id=fix_id,
        summary=f"Tighten the approved title for slide {entry.slide_number}.",
        source_action_ids=[action.action_id],
        source_finding_ids=[action.finding_id],
        scope=action.scope,
        affected_slide_range=_range_for_action(action),
        affected_batch_ids=_dedupe([entry.batch_id or action.target_batch_id or ""]),
        affected_section_ids=_dedupe([entry.section_id or ""]),
        target_artifacts=artifacts,
        selectors=[f"slides[slide_number={entry.slide_number}]", f"entries[slide_number={entry.slide_number}]"],
        delta_ids=delta_ids,
        rationale=action.rationale,
        downstream_rerun_stages=_stages_for_artifacts(artifacts),
        approval_requirement=_approval_requirement(artifacts),
        risk_level=_risk_level(action.scope, artifacts),
    )
    return fix, artifacts


def _make_terminology_fix(
    action: RemediationAction,
    slide_ledger: SlideLedger,
    blueprint: Blueprint,
    deck_constitution: DeckConstitution,
    builder: _DeltaBuilder,
) -> tuple[UpstreamFixProposal, list[UpstreamArtifactName]] | None:
    slide_range = _range_for_action(action)
    entries = _entries_in_range(slide_ledger, slide_range)
    slides_by_number = {slide.slide_number: slide for slide in blueprint.slides}
    delta_ids: list[str] = []
    selectors: list[str] = []
    for entry in entries:
        slide = slides_by_number.get(entry.slide_number)
        for field_name in ("title", "one_line_takeaway", "main_message"):
            current_value = getattr(slide, field_name) if slide is not None else getattr(entry, field_name)
            proposed_value, preferred = _term_replacements(current_value, deck_constitution)
            if proposed_value is None or proposed_value == current_value:
                continue
            selectors.extend([f"slides[slide_number={entry.slide_number}]", f"entries[slide_number={entry.slide_number}]"])
            delta_ids.append(
                builder.add(
                    fix_id=f"fix-{action.finding_id}",
                    target_artifact=UpstreamArtifactName.BLUEPRINT,
                    selector=f"slides[slide_number={entry.slide_number}]",
                    field_path=field_name,
                    operation=DeltaOperation.REPLACE,
                    current_value=current_value,
                    proposed_value=proposed_value,
                    rationale=f"Replace discouraged terminology with the approved term `{preferred}`.",
                )
            )
            delta_ids.append(
                builder.add(
                    fix_id=f"fix-{action.finding_id}",
                    target_artifact=UpstreamArtifactName.SLIDE_LEDGER,
                    selector=f"entries[slide_number={entry.slide_number}]",
                    field_path=field_name,
                    operation=DeltaOperation.REPLACE,
                    current_value=getattr(entry, field_name),
                    proposed_value=proposed_value,
                    rationale=f"Keep the ledger synchronized to the approved `{preferred}` term.",
                )
            )
    if not delta_ids:
        return None
    artifacts = [UpstreamArtifactName.BLUEPRINT, UpstreamArtifactName.SLIDE_LEDGER]
    fix = UpstreamFixProposal(
        fix_id=f"fix-{action.finding_id}",
        summary=f"Normalize approved terminology across slides {slide_range.label()}.",
        source_action_ids=[action.action_id],
        source_finding_ids=[action.finding_id],
        scope=action.scope,
        affected_slide_range=slide_range,
        affected_batch_ids=_dedupe([entry.batch_id or action.target_batch_id or "" for entry in entries]),
        affected_section_ids=_dedupe([entry.section_id or "" for entry in entries]),
        target_artifacts=artifacts,
        selectors=_dedupe(selectors),
        delta_ids=delta_ids,
        rationale=action.rationale,
        downstream_rerun_stages=_stages_for_artifacts(artifacts),
        approval_requirement=_approval_requirement(artifacts),
        risk_level=_risk_level(action.scope, artifacts),
    )
    return fix, artifacts


def _make_asset_request_fix(
    action: RemediationAction,
    slide_ledger: SlideLedger,
    blueprint: Blueprint,
    asset_requests: AssetRequests | None,
    asset_manifest: AssetManifest,
    builder: _DeltaBuilder,
) -> tuple[UpstreamFixProposal, list[UpstreamArtifactName]] | None:
    request = _request_for_action(asset_requests, action)
    if request is None:
        return None
    entries = _entries_in_range(slide_ledger, _range_for_action(action))
    if not entries:
        return None
    entry = entries[0]
    slide = next((item for item in blueprint.slides if item.slide_number == entry.slide_number), None)
    matched_assets = _asset_records_for_action(asset_manifest, action)
    delta_ids: list[str] = []
    if request.page_hint is None:
        page_number = next((asset.provenance.page_number for asset in matched_assets if asset.provenance.page_number is not None), None)
        if page_number is not None:
            delta_ids.append(
                builder.add(
                    fix_id=f"fix-{action.finding_id}",
                    target_artifact=UpstreamArtifactName.ASSET_REQUESTS,
                    selector=f"requests[slide_id={request.slide_id}]",
                    field_path="page_hint",
                    operation=DeltaOperation.INSERT,
                    current_value=None,
                    proposed_value=page_number,
                    rationale="Anchor the crop request to the exact reviewed source page for the next bounded rerun.",
                )
            )
    candidate_options = _dedupe(
        [
            _clean_title_candidate(slide.title) if slide is not None else "",
            _clean_title_candidate(entry.title),
            _clean_title_candidate(entry.one_line_takeaway),
        ]
    )
    candidate_options = [option for option in candidate_options if option and option != request.crop_subject_hint]
    if candidate_options:
        option_models = [
            DeltaOption(
                option_id=f"fix-{action.finding_id}-crop-hint-{index}",
                label=option,
                value=option,
                rationale="Use a tighter subject hint so the crop worker can isolate the intended evidence object.",
            )
            for index, option in enumerate(candidate_options[:3], start=1)
        ]
        delta_ids.append(
            builder.add(
                fix_id=f"fix-{action.finding_id}",
                target_artifact=UpstreamArtifactName.ASSET_REQUESTS,
                selector=f"requests[slide_id={request.slide_id}]",
                field_path="crop_subject_hint",
                operation=DeltaOperation.CHOOSE_ONE,
                current_value=request.crop_subject_hint,
                options=option_models,
                rationale="Refine the crop subject hint before reopening source-crop execution.",
            )
        )
    if not delta_ids:
        return None
    artifacts = [UpstreamArtifactName.ASSET_REQUESTS]
    fix = UpstreamFixProposal(
        fix_id=f"fix-{action.finding_id}",
        summary=f"Refine the source-crop request for slide {entry.slide_number}.",
        source_action_ids=[action.action_id],
        source_finding_ids=[action.finding_id],
        scope=action.scope,
        affected_slide_range=_range_for_action(action),
        affected_batch_ids=_dedupe([entry.batch_id or action.target_batch_id or ""]),
        affected_section_ids=_dedupe([entry.section_id or ""]),
        target_artifacts=artifacts,
        selectors=[f"requests[slide_id={request.slide_id}]"],
        delta_ids=delta_ids,
        rationale=action.rationale,
        downstream_rerun_stages=_stages_for_artifacts(artifacts, asset_request=request),
        approval_requirement=_approval_requirement(artifacts),
        risk_level=_risk_level(action.scope, artifacts),
    )
    return fix, artifacts


def _make_layout_fix(
    action: RemediationAction,
    slide_ledger: SlideLedger,
    blueprint: Blueprint,
    layout_library: LayoutLibrary,
    builder: _DeltaBuilder,
) -> tuple[UpstreamFixProposal, list[UpstreamArtifactName]] | None:
    entries = _entries_in_range(slide_ledger, _range_for_action(action))
    if not entries:
        return None
    entry = entries[0]
    alternatives = _compatible_patterns(
        layout_library,
        visual_type=entry.visual_type,
        current_pattern_id=entry.layout_pattern_id,
    )
    if not alternatives:
        return None
    options = [
        DeltaOption(
            option_id=f"fix-{action.finding_id}-layout-{index}",
            label=pattern.name,
            value=pattern.pattern_id,
            rationale=f"Use the `{pattern.pattern_id}` pattern to stay inside the approved layout library.",
        )
        for index, pattern in enumerate(alternatives[:3], start=1)
    ]
    delta_ids = [
        builder.add(
            fix_id=f"fix-{action.finding_id}",
            target_artifact=UpstreamArtifactName.BLUEPRINT,
            selector=f"slides[slide_number={entry.slide_number}]",
            field_path="layout_pattern_id",
            operation=DeltaOperation.CHOOSE_ONE,
            current_value=next((slide.layout_pattern_id for slide in blueprint.slides if slide.slide_number == entry.slide_number), entry.layout_pattern_id),
            options=options,
            rationale="Approve a bounded layout reassignment before the next compile.",
        ),
        builder.add(
            fix_id=f"fix-{action.finding_id}",
            target_artifact=UpstreamArtifactName.SLIDE_LEDGER,
            selector=f"entries[slide_number={entry.slide_number}]",
            field_path="layout_pattern_id",
            operation=DeltaOperation.CHOOSE_ONE,
            current_value=entry.layout_pattern_id,
            options=options,
            rationale="Keep the ledger aligned to the approved layout pattern choice.",
        ),
    ]
    artifacts = [UpstreamArtifactName.BLUEPRINT, UpstreamArtifactName.SLIDE_LEDGER, UpstreamArtifactName.LAYOUT_LIBRARY]
    fix = UpstreamFixProposal(
        fix_id=f"fix-{action.finding_id}",
        summary=f"Reassign slide {entry.slide_number} to an approved layout-library pattern.",
        source_action_ids=[action.action_id],
        source_finding_ids=[action.finding_id],
        scope=action.scope,
        affected_slide_range=_range_for_action(action),
        affected_batch_ids=_dedupe([entry.batch_id or action.target_batch_id or ""]),
        affected_section_ids=_dedupe([entry.section_id or ""]),
        target_artifacts=artifacts,
        selectors=[f"slides[slide_number={entry.slide_number}]", f"entries[slide_number={entry.slide_number}]"],
        delta_ids=delta_ids,
        rationale=action.rationale,
        downstream_rerun_stages=_stages_for_artifacts(artifacts),
        approval_requirement=_approval_requirement(artifacts),
        risk_level=_risk_level(action.scope, artifacts),
    )
    return fix, artifacts


def _make_visual_route_fix(
    action: RemediationAction,
    slide_ledger: SlideLedger,
    blueprint: Blueprint,
    viz_spec: VizSpecSet | None,
    layout_library: LayoutLibrary,
    builder: _DeltaBuilder,
) -> tuple[UpstreamFixProposal, list[UpstreamArtifactName]] | None:
    spec = _spec_for_action(viz_spec, action)
    if spec is None or spec.fallback_visual is None or spec.fallback_visual == spec.visual_type:
        return None
    entries = _entries_in_range(slide_ledger, _range_for_action(action))
    if not entries:
        return None
    entry = entries[0]
    alternatives = _compatible_patterns(
        layout_library,
        visual_type=spec.fallback_visual,
        current_pattern_id=spec.layout_pattern_id,
    )
    layout_value = alternatives[0].pattern_id if alternatives else spec.layout_pattern_id
    delta_ids = [
        builder.add(
            fix_id=f"fix-{action.finding_id}",
            target_artifact=UpstreamArtifactName.BLUEPRINT,
            selector=f"slides[slide_number={entry.slide_number}]",
            field_path="visual_type",
            operation=DeltaOperation.REPLACE,
            current_value=next((slide.visual_type.value for slide in blueprint.slides if slide.slide_number == entry.slide_number), entry.visual_type.value),
            proposed_value=spec.fallback_visual.value,
            rationale="Promote the recorded fallback visual route before rerendering.",
        ),
        builder.add(
            fix_id=f"fix-{action.finding_id}",
            target_artifact=UpstreamArtifactName.SLIDE_LEDGER,
            selector=f"entries[slide_number={entry.slide_number}]",
            field_path="visual_type",
            operation=DeltaOperation.REPLACE,
            current_value=entry.visual_type.value,
            proposed_value=spec.fallback_visual.value,
            rationale="Keep the ledger synchronized to the approved fallback route.",
        ),
        builder.add(
            fix_id=f"fix-{action.finding_id}",
            target_artifact=UpstreamArtifactName.VIZ_SPEC,
            selector=f"specs[slide_id={spec.slide_id or entry.slide_id}]",
            field_path="visual_type",
            operation=DeltaOperation.REPLACE,
            current_value=spec.visual_type.value,
            proposed_value=spec.fallback_visual.value,
            rationale="Update the structured-visual spec to the bounded fallback type.",
        ),
        builder.add(
            fix_id=f"fix-{action.finding_id}",
            target_artifact=UpstreamArtifactName.VIZ_SPEC,
            selector=f"specs[slide_id={spec.slide_id or entry.slide_id}]",
            field_path="layout_pattern_id",
            operation=DeltaOperation.REPLACE,
            current_value=spec.layout_pattern_id,
            proposed_value=layout_value,
            rationale="Use a layout pattern that supports the approved fallback visual type.",
        ),
    ]
    artifacts = [UpstreamArtifactName.BLUEPRINT, UpstreamArtifactName.SLIDE_LEDGER, UpstreamArtifactName.VIZ_SPEC]
    fix = UpstreamFixProposal(
        fix_id=f"fix-{action.finding_id}",
        summary=f"Switch slide {entry.slide_number} to its bounded structured-visual fallback.",
        source_action_ids=[action.action_id],
        source_finding_ids=[action.finding_id],
        scope=action.scope,
        affected_slide_range=_range_for_action(action),
        affected_batch_ids=_dedupe([entry.batch_id or action.target_batch_id or ""]),
        affected_section_ids=_dedupe([entry.section_id or ""]),
        target_artifacts=artifacts,
        selectors=[f"slides[slide_number={entry.slide_number}]", f"entries[slide_number={entry.slide_number}]", f"specs[slide_id={spec.slide_id or entry.slide_id}]"],
        delta_ids=delta_ids,
        rationale=action.rationale,
        downstream_rerun_stages=_stages_for_artifacts(artifacts, viz_spec=spec),
        approval_requirement=_approval_requirement(artifacts),
        risk_level=_risk_level(action.scope, artifacts),
    )
    return fix, artifacts


def _candidate_manual_artifacts(action: RemediationAction) -> list[UpstreamArtifactName]:
    if action.owner == RemediationOwner.UPSTREAM_CONTENT_STORY:
        return [UpstreamArtifactName.BLUEPRINT, UpstreamArtifactName.DECK_CONSTITUTION, UpstreamArtifactName.SLIDE_LEDGER]
    if action.owner == RemediationOwner.CROP_SOURCE_ASSET:
        return [UpstreamArtifactName.ASSET_REQUESTS, UpstreamArtifactName.BLUEPRINT]
    if action.owner == RemediationOwner.STRUCTURED_VISUAL:
        return [UpstreamArtifactName.VIZ_SPEC, UpstreamArtifactName.BLUEPRINT, UpstreamArtifactName.LAYOUT_LIBRARY]
    if action.owner == RemediationOwner.COMPILER_LAYOUT:
        return [UpstreamArtifactName.BLUEPRINT, UpstreamArtifactName.LAYOUT_LIBRARY, UpstreamArtifactName.SLIDE_LEDGER]
    return [UpstreamArtifactName.DECK_CONSTITUTION]


def _manual_blocked_issue(
    action: RemediationAction,
    slide_ledger: SlideLedger,
    reason: str,
) -> BlockedManualUpstreamIssue:
    slide_range = _range_for_action(action)
    entries = _entries_in_range(slide_ledger, slide_range)
    return BlockedManualUpstreamIssue(
        issue_id=f"blocked-{action.finding_id}",
        summary=f"Manual review required for {action.finding_id}.",
        source_action_ids=[action.action_id],
        source_finding_ids=[action.finding_id],
        scope=action.scope,
        affected_slide_range=slide_range,
        affected_batch_ids=_dedupe([entry.batch_id or action.target_batch_id or "" for entry in entries]),
        affected_section_ids=_dedupe([entry.section_id or "" for entry in entries]),
        candidate_target_artifacts=_candidate_manual_artifacts(action),
        rationale=action.rationale,
        downstream_rerun_stages=_ordered_reruns(action.rerun_stages or ["compile-pptx", "qa-deck", "orchestrate-large-deck"]),
        approval_requirement="manual-architecture-review",
        risk_level=FixRiskLevel.HIGH,
        blocked_reason=reason,
        suggested_manual_next_step="Review the deck-level issue manually, narrow the approved scope, then rerun Phase 13.",
    )


def _packet_key(fix: UpstreamFixProposal) -> str:
    family = _artifact_family_name(fix.target_artifacts)
    if fix.scope == RemediationScope.LOCAL_CHANGE_ONLY:
        return f"slide-{fix.affected_slide_range.label()}-{family}"
    if fix.scope == RemediationScope.SECTION_LEVEL_REFLOW:
        section_key = fix.affected_section_ids[0] if fix.affected_section_ids else fix.affected_slide_range.label()
        return f"section-{section_key}-{family}"
    return f"deck-{family}"


def _build_packets(fixes: list[UpstreamFixProposal]) -> list[ApprovalPacket]:
    grouped: dict[str, list[UpstreamFixProposal]] = defaultdict(list)
    for fix in fixes:
        grouped[_packet_key(fix)].append(fix)

    packets: list[ApprovalPacket] = []
    for key, group in sorted(grouped.items()):
        slide_range = SlideRange(
            start=min(fix.affected_slide_range.start for fix in group),
            end=max(fix.affected_slide_range.end for fix in group),
        )
        artifact_values = _dedupe([artifact.value for fix in group for artifact in fix.target_artifacts])
        artifact_models = [UpstreamArtifactName(value) for value in artifact_values]
        scope_rank = {
            RemediationScope.LOCAL_CHANGE_ONLY: 1,
            RemediationScope.SECTION_LEVEL_REFLOW: 2,
            RemediationScope.DECK_LEVEL_REFLOW: 3,
        }
        scope = max(group, key=lambda fix: scope_rank[fix.scope]).scope
        packet_id = f"packet-{_slug(key)}"
        expected_reruns = _ordered_reruns([stage for fix in group for stage in fix.downstream_rerun_stages])
        independently_safe = not (
            set(artifact_models) & {UpstreamArtifactName.DESIGN_SYSTEM, UpstreamArtifactName.LAYOUT_LIBRARY}
            or scope == RemediationScope.DECK_LEVEL_REFLOW
        )
        packets.append(
            ApprovalPacket(
                packet_id=packet_id,
                objective=_packet_objective(scope, artifact_models, slide_range),
                scope=scope,
                included_fix_ids=[fix.fix_id for fix in group],
                affected_slide_range=slide_range,
                affected_batch_ids=_dedupe([batch_id for fix in group for batch_id in fix.affected_batch_ids]),
                affected_section_ids=_dedupe([section_id for fix in group for section_id in fix.affected_section_ids]),
                target_artifacts=artifact_models,
                rationale_summary=_dedupe([fix.summary for fix in group])[0],
                risk_summary=f"{max((fix.risk_level for fix in group), default=FixRiskLevel.LOW).value} risk approval packet.",
                required_approvals=_required_approvals(artifact_models),
                expected_downstream_reruns=expected_reruns,
                approval_mode=PacketApprovalMode.INDEPENDENT if independently_safe else PacketApprovalMode.BUNDLE_REQUIRED,
                safe_to_approve_independently=independently_safe,
            )
        )
    return packets


def author_upstream_fixes(
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
    *,
    asset_requests: AssetRequests | None = None,
    viz_spec: VizSpecSet | None = None,
    pointer_root: str | None = None,
) -> UpstreamFixAuthoringOutputs:
    del batch_manifest
    del context_lock
    del slide_build_linkage
    del build_manifest
    del design_system
    del viz_manifest

    builder = _DeltaBuilder()
    execution_by_finding = {item.finding_id: item for item in remediation_execution_report.items}
    slides_by_number = {slide.slide_number: slide for slide in blueprint.slides}
    candidate_actions = _candidate_actions(remediation_plan, remediation_execution_report, qa_report)

    fixes: list[UpstreamFixProposal] = []
    blocked_manual_items: list[BlockedManualUpstreamIssue] = []
    deferred_or_noop_action_ids: list[str] = []

    for action in candidate_actions:
        execution_item = execution_by_finding.get(action.finding_id)
        if execution_item is not None and execution_item.execution_status == RemediationExecutionStatus.APPLIED:
            continue

        if action.owner == RemediationOwner.UPSTREAM_CONTENT_STORY:
            if action.scope == RemediationScope.DECK_LEVEL_REFLOW:
                blocked_manual_items.append(
                    _manual_blocked_issue(
                        action,
                        slide_ledger,
                        "Deck-level upstream story changes exceed the bounded authoring threshold for this phase.",
                    )
                )
                continue
            entries = _entries_in_range(slide_ledger, _range_for_action(action))
            if not entries:
                blocked_manual_items.append(
                    _manual_blocked_issue(
                        action,
                        slide_ledger,
                        "No slide-ledger entries matched the unresolved upstream action.",
                    )
                )
                continue
            if action.category in {"clarity", "content-drift"}:
                result = _make_title_fix(action, slides_by_number.get(entries[0].slide_number), entries[0], builder)
                if result is not None:
                    fix, _ = result
                    fixes.append(fix)
                    continue
            if action.category in {"terminology", "title-style", "section-drift"}:
                result = _make_terminology_fix(action, slide_ledger, blueprint, deck_constitution, builder)
                if result is not None:
                    fix, _ = result
                    fixes.append(fix)
                    continue
            blocked_manual_items.append(
                _manual_blocked_issue(
                    action,
                    slide_ledger,
                    "The upstream content change could not be reduced to explicit bounded deltas from the current state.",
                )
            )
            continue

        if action.owner == RemediationOwner.CROP_SOURCE_ASSET:
            result = _make_asset_request_fix(action, slide_ledger, blueprint, asset_requests, asset_manifest, builder)
            if result is not None:
                fix, _ = result
                fixes.append(fix)
                continue
            if action.disposition == RemediationDisposition.SAFE_TO_DEFER:
                deferred_or_noop_action_ids.append(action.action_id)
                continue
            blocked_manual_items.append(
                _manual_blocked_issue(
                    action,
                    slide_ledger,
                    "The source-asset issue needs a manual crop review decision before bounded upstream deltas can be prepared.",
                )
            )
            continue

        if action.owner == RemediationOwner.STRUCTURED_VISUAL:
            result = _make_visual_route_fix(action, slide_ledger, blueprint, viz_spec, layout_library, builder)
            if result is not None:
                fix, _ = result
                fixes.append(fix)
                continue
            if action.disposition == RemediationDisposition.SAFE_TO_DEFER:
                deferred_or_noop_action_ids.append(action.action_id)
                continue
            blocked_manual_items.append(
                _manual_blocked_issue(
                    action,
                    slide_ledger,
                    "The structured-visual issue needs a manual design decision beyond the bounded fallback rules in this phase.",
                )
            )
            continue

        if action.owner == RemediationOwner.COMPILER_LAYOUT:
            if action.scope == RemediationScope.LOCAL_CHANGE_ONLY and action.category in {"layout", "design-drift", "density", "content-drift"}:
                result = _make_layout_fix(action, slide_ledger, blueprint, layout_library, builder)
                if result is not None:
                    fix, _ = result
                    fixes.append(fix)
                    continue
            if action.disposition == RemediationDisposition.SAFE_TO_DEFER:
                deferred_or_noop_action_ids.append(action.action_id)
                continue
            blocked_manual_items.append(
                _manual_blocked_issue(
                    action,
                    slide_ledger,
                    "The compiler/layout issue remains outside bounded upstream authoring and still needs manual narrowing.",
                )
            )
            continue

        if action.disposition == RemediationDisposition.SAFE_TO_DEFER:
            deferred_or_noop_action_ids.append(action.action_id)
            continue

        blocked_manual_items.append(
            _manual_blocked_issue(
                action,
                slide_ledger,
                "The unresolved remediation action does not map to a bounded upstream authoring template.",
            )
        )

    packets = _build_packets(fixes)
    packet_ids = [packet.packet_id for packet in packets]
    packet_id_by_fix = {
        fix_id: packet.packet_id
        for packet in packets
        for fix_id in packet.included_fix_ids
    }
    artifact_impact: dict[UpstreamArtifactName, ArtifactImpactSummary] = {}
    for fix in fixes:
        packet_id = packet_id_by_fix.get(fix.fix_id)
        for artifact in fix.target_artifacts:
            current = artifact_impact.setdefault(
                artifact,
                ArtifactImpactSummary(artifact=artifact, fix_count=0, delta_count=0, packet_ids=[]),
            )
            current.fix_count += 1
            current.delta_count += sum(1 for delta in builder.deltas if delta.fix_id == fix.fix_id and delta.target_artifact == artifact)
            if packet_id is not None and packet_id not in current.packet_ids:
                current.packet_ids.append(packet_id)

    rerun_counts = Counter(stage for fix in fixes for stage in fix.downstream_rerun_stages)
    plan_id = f"upstream-fix-plan-{_slug(remediation_plan.deck_title)}"
    upstream_fix_plan = UpstreamFixPlan(
        plan_id=plan_id,
        deck_title=remediation_plan.deck_title,
        source_remediation_plan_id=remediation_plan.plan_id,
        source_execution_report_id=remediation_execution_report.report_id,
        total_issues_reviewed=len(candidate_actions),
        actionable_upstream_issue_count=len(fixes),
        deferred_or_noop_count=len(_dedupe(deferred_or_noop_action_ids)),
        blocked_manual_count=len(blocked_manual_items),
        fixes=fixes,
        deferred_or_noop_action_ids=_dedupe(deferred_or_noop_action_ids),
        approval_packets=packets,
        artifact_impact_summary=list(artifact_impact.values()),
        rerun_impact_summary=dict(rerun_counts),
        blocked_manual_items=blocked_manual_items,
    )
    approval_packet = ApprovalPacketSet(
        deck_title=remediation_plan.deck_title,
        source_plan_id=plan_id,
        source_execution_report_id=remediation_execution_report.report_id,
        packets=packets,
    )
    finding_ids_by_fix = {
        fix.fix_id: list(fix.source_finding_ids)
        for fix in fixes
    }
    annotated_deltas = [
        delta.model_copy(update={"source_finding_ids": finding_ids_by_fix.get(delta.fix_id, list(delta.source_finding_ids))})
        for delta in builder.deltas
    ]
    authoring_deltas = AuthoringDeltas(
        deck_title=remediation_plan.deck_title,
        source_plan_id=plan_id,
        source_execution_report_id=remediation_execution_report.report_id,
        deltas=annotated_deltas,
    )

    resolved_pointer_root = pointer_root or state_capsule.canonical_state_root or "state"
    updated_state_capsule = _update_state_capsule(
        state_capsule,
        pointer_root=resolved_pointer_root,
        packet_ids=packet_ids,
        fix_ids=[fix.fix_id for fix in fixes],
        blocked_items=blocked_manual_items,
    )
    updated_handoff_packet = _update_handoff_packet(
        handoff_packet,
        packet_ids=packet_ids,
        fix_ids=[fix.fix_id for fix in fixes],
        blocked_items=blocked_manual_items,
    )
    return UpstreamFixAuthoringOutputs(
        upstream_fix_plan=upstream_fix_plan,
        approval_packet=approval_packet,
        authoring_deltas=authoring_deltas,
        state_capsule=updated_state_capsule,
        handoff_packet=updated_handoff_packet,
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


def author_upstream_fixes_from_files(
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
) -> UpstreamFixAuthoringOutputs:
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
    asset_requests = _load_optional_state(asset_requests_path, "asset_requests")
    viz_spec = _load_optional_state(viz_spec_path, "viz_spec")

    if remediation_plan.schema_name != "remediation_plan":
        raise TypeError(f"expected remediation_plan, found {remediation_plan.schema_name}")
    if remediation_execution_report.schema_name != "remediation_execution_report":
        raise TypeError(f"expected remediation_execution_report, found {remediation_execution_report.schema_name}")
    if batch_manifest.schema_name != "batch_manifest":
        raise TypeError(f"expected batch_manifest, found {batch_manifest.schema_name}")
    if context_lock.schema_name != "context_lock":
        raise TypeError(f"expected context_lock, found {context_lock.schema_name}")
    if handoff_packet.schema_name != "handoff_packet":
        raise TypeError(f"expected handoff_packet, found {handoff_packet.schema_name}")
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

    return author_upstream_fixes(
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


def write_upstream_fix_outputs(
    outputs: UpstreamFixAuthoringOutputs,
    output_dir: str | Path,
) -> dict[str, Path]:
    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    return {
        "upstream_fix_plan": save_state_file(
            outputs.upstream_fix_plan,
            resolved_output_dir / DEFAULT_STATE_FILENAMES["upstream_fix_plan"],
        ),
        "approval_packet": save_state_file(
            outputs.approval_packet,
            resolved_output_dir / DEFAULT_STATE_FILENAMES["approval_packet"],
        ),
        "authoring_deltas": save_state_file(
            outputs.authoring_deltas,
            resolved_output_dir / DEFAULT_STATE_FILENAMES["authoring_deltas"],
        ),
        "state_capsule": save_state_file(
            outputs.state_capsule,
            resolved_output_dir / DEFAULT_STATE_FILENAMES["state_capsule"],
        ),
        "handoff_packet": save_state_file(
            outputs.handoff_packet,
            resolved_output_dir / DEFAULT_STATE_FILENAMES["handoff_packet"],
        ),
    }


