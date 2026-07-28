"""Deterministic large-deck orchestration and continuity controls."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import re

from ..compat.legacy_non_pptx import WorkflowGate
from ..pptx_compiler import BuildManifest, SlideBuildLinkage, load_pptx_compile_file
from ..compat.legacy_non_pptx import (
    BatchIntent,
    BatchBoundaryContinuityAlert,
    BatchChunk,
    BatchManifest,
    BatchMode,
    Blueprint,
    ContextLock,
    ContextLockDecision,
    ContractModel,
    DeckConstitution,
    DeckHierarchyLevel,
    DeckHierarchyNode,
    DeckMode,
    DEFAULT_STATE_FILENAMES,
    DesignSystem,
    FindingStatus,
    HandoffPacket,
    LayoutLibrary,
    LockedDesignSystem,
    QAFinding,
    QALayer,
    QARecommendationType,
    QAReport,
    QASeverity,
    QAStatus,
    RemediationAction,
    RemediationBatch,
    RemediationDisposition,
    RemediationExecutionAction,
    RemediationOwner,
    RemediationPlan,
    RemediationScope,
    ScaleMode,
    SlideLedger,
    SlideLedgerEntry,
    SlideRange,
    StageStatus,
    StateCapsule,
    StateFilePointer,
    WorkflowPlan,
    load_state_file,
    save_state_file,
)
from .state_schemas import CompileEligibility, QAVerdictSummary, normalize_continuity_guidance_and_mirror
from .state_schemas import QASlideResult


CONTINUITY_SCALE_MODES = {
    ScaleMode.EXTENDED,
    ScaleMode.LARGE_DECK,
    ScaleMode.MEGA_DECK,
}

MULTI_BATCH_SCALE_MODES = {
    ScaleMode.LARGE_DECK,
    ScaleMode.MEGA_DECK,
}

SCALE_ORDER = [
    ScaleMode.COMPACT,
    ScaleMode.STANDARD,
    ScaleMode.EXTENDED,
    ScaleMode.LARGE_DECK,
    ScaleMode.MEGA_DECK,
]

SKILL_OWNER_MAP = {
    "deck-orchestrator": RemediationOwner.UPSTREAM_CONTENT_STORY,
    "document-asset-crop": RemediationOwner.CROP_SOURCE_ASSET,
    "structured-visuals": RemediationOwner.STRUCTURED_VISUAL,
    "pptx-compiler": RemediationOwner.COMPILER_LAYOUT,
    "deck-qa": RemediationOwner.QA_THRESHOLD_POLICY,
}

TERMINOLOGY_ALERT_THRESHOLD = 0.9
DESIGN_TOKEN_ALERT_THRESHOLD = 0.95
TERM_STOPWORDS = frozenset(
    {
        "about",
        "after",
        "against",
        "appendix",
        "before",
        "between",
        "core",
        "deck",
        "from",
        "have",
        "into",
        "main",
        "only",
        "section",
        "should",
        "slide",
        "slides",
        "story",
        "than",
        "that",
        "their",
        "there",
        "these",
        "this",
        "through",
        "with",
    }
)


class LargeDeckOutputs(ContractModel):
    batch_manifest: BatchManifest
    context_lock: ContextLock
    handoff_packet: HandoffPacket
    state_capsule: StateCapsule
    remediation_plan: RemediationPlan
    slide_ledger: SlideLedger
    slide_build_linkage: SlideBuildLinkage | None = None


def supports_continuity_controls(scale_mode: ScaleMode) -> bool:
    return scale_mode in CONTINUITY_SCALE_MODES


def supports_multi_batch(scale_mode: ScaleMode) -> bool:
    return scale_mode in MULTI_BATCH_SCALE_MODES


def _clone_entry(entry: SlideLedgerEntry) -> SlideLedgerEntry:
    return SlideLedgerEntry.model_validate(entry.model_dump(mode="json", exclude_none=True))


def _range_contains(outer: SlideRange, inner: SlideRange) -> bool:
    return outer.start <= inner.start and inner.end <= outer.end


def _range_labels(ranges: list[SlideRange]) -> list[str]:
    return [item.label() for item in ranges]


def _slug(text: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in text.lower()).strip("-") or "item"


def _batch_size_for_scale(scale_mode: ScaleMode, overrides: dict[str, int] | None = None) -> int:
    override_map = overrides or {}
    override_value = override_map.get(scale_mode.value)
    if override_value is not None:
        if override_value < 1:
            raise ValueError("batch size overrides must be positive integers")
        return override_value
    if scale_mode == ScaleMode.MEGA_DECK:
        return 5
    if scale_mode == ScaleMode.LARGE_DECK:
        return 6
    if scale_mode == ScaleMode.EXTENDED:
        return 8
    return 9999


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _scale_rank(scale_mode: ScaleMode) -> int:
    return SCALE_ORDER.index(scale_mode)


def _wider_scale(left: ScaleMode, right: ScaleMode) -> ScaleMode:
    return SCALE_ORDER[max(_scale_rank(left), _scale_rank(right))]


def _resolve_qa_policy_summary(qa_report: QAReport | None) -> tuple[QAVerdictSummary | None, str]:
    if qa_report is None:
        return None, "qa-report-unavailable"
    summary = getattr(qa_report, "verdict_summary", None)
    if summary is None:
        return None, "raw-qa-status"
    summary_status = getattr(getattr(summary, "qa_status", None), "value", getattr(summary, "qa_status", None))
    raw_status = getattr(getattr(qa_report, "qa_status", None), "value", getattr(qa_report, "qa_status", None))
    if summary_status is None or raw_status is None:
        return None, "raw-qa-status"
    if str(summary_status) != str(raw_status):
        return None, "raw-qa-status-mismatch-fallback"
    return summary, "verdict-summary"


def _resolve_compile_warning_count(
    qa_policy_summary: QAVerdictSummary | None,
    build_manifest: BuildManifest | None,
) -> tuple[int, str]:
    raw_build_warning_count = len(build_manifest.warnings) if build_manifest is not None else 0
    compatibility_warning_codes = (
        list(qa_policy_summary.compatibility_warning_codes)
        if qa_policy_summary is not None
        else []
    )
    if "build-warning-string-surface" in compatibility_warning_codes:
        if raw_build_warning_count > 0:
            return raw_build_warning_count, "structured-compatibility-code"
        return 1, "structured-compatibility-code"
    if raw_build_warning_count > 0:
        return raw_build_warning_count, "raw-build-manifest"
    return 0, "none"


def _resolve_blocking_count(
    qa_policy_summary: QAVerdictSummary | None,
    qa_report: QAReport | None,
) -> tuple[int, str]:
    raw_blocking_count = qa_report.summary.blocking_count if qa_report is not None else 0
    if qa_policy_summary is not None:
        structured_blocking_count = len(qa_policy_summary.blocking_reason_codes)
        if structured_blocking_count > 0:
            return structured_blocking_count, "verdict-summary"
        if qa_policy_summary.compile_eligibility == CompileEligibility.INELIGIBLE:
            return max(raw_blocking_count, 1), "verdict-summary"
    if raw_blocking_count > 0:
        return raw_blocking_count, "qa-summary"
    return 0, "none"


def _build_qa_slide_result_lookups(
    qa_report: QAReport | None,
) -> tuple[dict[str, QASlideResult], dict[int, QASlideResult]]:
    by_slide_id: dict[str, QASlideResult] = {}
    by_slide_number: dict[int, QASlideResult] = {}
    if qa_report is None:
        return by_slide_id, by_slide_number
    for result in qa_report.slide_results:
        if result.slide_id and result.slide_id not in by_slide_id:
            by_slide_id[result.slide_id] = result
        if result.slide_number not in by_slide_number:
            by_slide_number[result.slide_number] = result
    return by_slide_id, by_slide_number


def _resolve_entry_qa_status(
    entry: SlideLedgerEntry,
    qa_slide_results_by_id: dict[str, QASlideResult],
    qa_slide_results_by_number: dict[int, QASlideResult],
) -> tuple[QAStatus | None, str]:
    if entry.slide_id:
        slide_result = qa_slide_results_by_id.get(entry.slide_id)
        if slide_result is not None:
            return slide_result.qa_status, "qa-slide-result"
    slide_result = qa_slide_results_by_number.get(entry.slide_number)
    if slide_result is not None and (not slide_result.slide_id or slide_result.slide_id == entry.slide_id):
        return slide_result.qa_status, "qa-slide-result"
    if entry.qa_status is not None:
        return entry.qa_status, "slide-ledger-entry"
    return None, "unavailable"


def _has_batch_local_qa_signal(
    slide_ledger: SlideLedger,
    qa_report: QAReport | None,
) -> bool:
    qa_slide_results_by_id, qa_slide_results_by_number = _build_qa_slide_result_lookups(qa_report)
    if qa_slide_results_by_id or qa_slide_results_by_number:
        return True
    return any(entry.qa_status is not None for entry in slide_ledger.entries)


def _infer_scale_mode(
    workflow_plan: WorkflowPlan,
    slide_ledger: SlideLedger,
    build_manifest: BuildManifest | None,
    qa_report: QAReport | None,
) -> ScaleMode:
    qa_policy_summary, _ = _resolve_qa_policy_summary(qa_report)
    slide_count = build_manifest.slide_count if build_manifest is not None else len(slide_ledger.entries)
    section_count = len({entry.section_id for entry in slide_ledger.entries})
    appendix_count = sum(1 for entry in slide_ledger.entries if entry.deck_mode == DeckMode.APPENDIX)
    qa_finding_count = len(qa_report.findings) if qa_report is not None else 0
    build_warning_count, _ = _resolve_compile_warning_count(qa_policy_summary, build_manifest)
    blocking_count, _ = _resolve_blocking_count(qa_policy_summary, qa_report)

    inferred = ScaleMode.COMPACT
    if slide_count > 5 or section_count > 1 or appendix_count > 0:
        inferred = ScaleMode.STANDARD
    if slide_count > 12 or section_count > 3 or qa_finding_count >= 6:
        inferred = ScaleMode.EXTENDED
    if slide_count > 20 or section_count > 5 or qa_finding_count >= 12:
        inferred = ScaleMode.LARGE_DECK
    if slide_count > 40 or section_count > 8:
        inferred = ScaleMode.MEGA_DECK
    if build_warning_count >= 3 or blocking_count >= 3:
        inferred = _wider_scale(inferred, ScaleMode.EXTENDED)
    return _wider_scale(workflow_plan.scale_mode, inferred)


def _range_for_finding(finding: QAFinding) -> SlideRange:
    if finding.slide_range is not None:
        return finding.slide_range
    if finding.slide_number is None:
        raise ValueError(f"finding {finding.finding_id} is missing slide context")
    return SlideRange(start=finding.slide_number, end=finding.slide_number)


def _section_groups(entries: list[SlideLedgerEntry]) -> list[list[SlideLedgerEntry]]:
    groups: list[list[SlideLedgerEntry]] = []
    current: list[SlideLedgerEntry] = []
    current_key: tuple[str, str] | None = None
    for entry in entries:
        key = (entry.part_id or "main-story", entry.section_id or _slug(entry.section))
        if current_key is None or key == current_key:
            current.append(entry)
            current_key = key
            continue
        groups.append(current)
        current = [entry]
        current_key = key
    if current:
        groups.append(current)
    return groups


def _entries_in_range(slide_ledger: SlideLedger, slide_range: SlideRange) -> list[SlideLedgerEntry]:
    return [
        entry
        for entry in slide_ledger.entries
        if slide_range.start <= entry.slide_number <= slide_range.end
    ]


def _tokenize_text(*parts: str | None) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        if not part:
            continue
        for token in re.findall(r"[a-z0-9]+", part.lower()):
            if token.isdigit() or len(token) < 4 or token in TERM_STOPWORDS:
                continue
            tokens.add(token)
    return tokens


def _jaccard_change_rate(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    overlap = left & right
    return round(1.0 - (len(overlap) / len(union)), 3)


def _boundary_range(source: BatchChunk, target: BatchChunk) -> SlideRange:
    return SlideRange(
        start=min(source.slide_range.end, target.slide_range.start),
        end=max(source.slide_range.end, target.slide_range.start),
    )


def _numbering_change_rate(source: BatchChunk, target: BatchChunk) -> float:
    gap = max(target.slide_range.start - source.slide_range.end - 1, 0)
    overlap = max(source.slide_range.end - target.slide_range.start + 1, 0)
    discontinuity = gap + overlap
    if discontinuity == 0:
        return 0.0
    span = max(1, target.slide_range.end - source.slide_range.start + 1)
    return round(min(1.0, discontinuity / span), 3)


def _linked_qa_finding_ids(
    source: BatchChunk,
    target: BatchChunk,
    qa_report: QAReport | None,
) -> list[str]:
    if qa_report is None:
        return []
    source_end = source.slide_range.end
    target_start = target.slide_range.start
    linked: list[str] = []
    for finding in qa_report.findings:
        try:
            finding_range = _range_for_finding(finding)
        except ValueError:
            continue
        if finding_range.start <= source_end and finding_range.end >= target_start:
            linked.append(finding.finding_id)
    return _unique_strings(linked)


def _boundary_warning_codes(
    terminology_change_rate: float,
    numbering_change_rate: float,
    design_token_change_rate: float,
    qa_finding_ids: list[str],
) -> list[str]:
    codes: list[str] = []
    if terminology_change_rate >= TERMINOLOGY_ALERT_THRESHOLD:
        codes.append("terminology-change-rate-high")
    if numbering_change_rate > 0.0:
        codes.append("numbering-change-rate-high")
    if design_token_change_rate >= DESIGN_TOKEN_ALERT_THRESHOLD:
        codes.append("design-token-change-rate-high")
    if qa_finding_ids:
        codes.append("qa-linked-boundary-risk")
    return codes


def _continuity_alerts(
    slide_ledger: SlideLedger,
    batches: list[BatchChunk],
    qa_report: QAReport | None,
) -> list[BatchBoundaryContinuityAlert]:
    alerts: list[BatchBoundaryContinuityAlert] = []
    if len(batches) < 2:
        return alerts

    for source, target in zip(batches, batches[1:]):
        source_entries = _entries_in_range(slide_ledger, source.slide_range)
        target_entries = _entries_in_range(slide_ledger, target.slide_range)
        terminology_change_rate = _jaccard_change_rate(
            _tokenize_text(
                *(entry.title for entry in source_entries),
                *(entry.one_line_takeaway for entry in source_entries),
                *(entry.main_message for entry in source_entries),
            ),
            _tokenize_text(
                *(entry.title for entry in target_entries),
                *(entry.one_line_takeaway for entry in target_entries),
                *(entry.main_message for entry in target_entries),
            ),
        )
        design_token_change_rate = _jaccard_change_rate(
            {
                f"{entry.layout_pattern_id}|{entry.visual_type.value}|{entry.deck_mode.value}"
                for entry in source_entries
            },
            {
                f"{entry.layout_pattern_id}|{entry.visual_type.value}|{entry.deck_mode.value}"
                for entry in target_entries
            },
        )
        numbering_change_rate = _numbering_change_rate(source, target)
        qa_finding_ids = _linked_qa_finding_ids(source, target, qa_report)
        warning_codes = _boundary_warning_codes(
            terminology_change_rate,
            numbering_change_rate,
            design_token_change_rate,
            qa_finding_ids,
        )
        alerts.append(
            BatchBoundaryContinuityAlert(
                alert_id=f"continuity-{source.batch_id}-to-{target.batch_id}",
                source_batch_id=source.batch_id,
                target_batch_id=target.batch_id,
                boundary_slide_range=_boundary_range(source, target),
                terminology_change_rate=terminology_change_rate,
                numbering_change_rate=numbering_change_rate,
                design_token_change_rate=design_token_change_rate,
                warning_codes=warning_codes,
                qa_finding_ids=qa_finding_ids,
                summary=(
                    f"Boundary {source.batch_id} -> {target.batch_id}: terminology {terminology_change_rate:.2f}, "
                    f"numbering {numbering_change_rate:.2f}, design-token {design_token_change_rate:.2f}."
                ),
            )
        )
    return alerts


def _boundary_alert_warnings(alerts: list[BatchBoundaryContinuityAlert]) -> list[str]:
    warnings: list[str] = []
    for alert in alerts:
        if not alert.warning_codes:
            continue
        labels: list[str] = []
        if "terminology-change-rate-high" in alert.warning_codes:
            labels.append(f"terminology shift {alert.terminology_change_rate:.2f}")
        if "numbering-change-rate-high" in alert.warning_codes:
            labels.append(f"numbering shift {alert.numbering_change_rate:.2f}")
        if "design-token-change-rate-high" in alert.warning_codes:
            labels.append(f"design-token shift {alert.design_token_change_rate:.2f}")
        if "qa-linked-boundary-risk" in alert.warning_codes:
            labels.append(f"linked QA findings {', '.join(alert.qa_finding_ids)}")
        warnings.append(
            f"Boundary {alert.source_batch_id} -> {alert.target_batch_id} needs continuity attention: {'; '.join(labels)}."
        )
    return warnings


def _batch_for_range(batches: list[BatchChunk], slide_range: SlideRange) -> BatchChunk | None:
    matches = [batch for batch in batches if _range_contains(batch.slide_range, slide_range)]
    if not matches:
        return None
    matches.sort(key=lambda batch: (batch.slide_range.end - batch.slide_range.start, batch.slide_range.start))
    return matches[0]


def renumber_slide_ledger(slide_ledger: SlideLedger) -> SlideLedger:
    entries = [_clone_entry(entry) for entry in slide_ledger.entries]
    old_to_new = {entry.slide_number: index for index, entry in enumerate(entries, start=1)}
    for index, entry in enumerate(entries, start=1):
        entry.slide_number = index
        entry.depends_on = [old_to_new[number] for number in entry.depends_on if number in old_to_new]
    continuity_notes = list(slide_ledger.continuity_notes)
    if not any("lineage" in note.lower() for note in continuity_notes):
        continuity_notes.append("Renumber slides through the ledger only; preserve slide_id and lineage_id across revisions.")
    return SlideLedger(
        deck_title=slide_ledger.deck_title,
        entries=entries,
        continuity_notes=continuity_notes,
    )


def insert_slide_entry(
    slide_ledger: SlideLedger,
    entry: SlideLedgerEntry,
    *,
    after_slide_number: int | None = None,
    after_slide_id: str | None = None,
) -> SlideLedger:
    entries = [_clone_entry(item) for item in slide_ledger.entries]
    if any(item.slide_id == entry.slide_id for item in entries):
        raise ValueError(f"slide_id {entry.slide_id!r} already exists in the ledger")

    insert_at = 0
    if after_slide_id is not None:
        for index, item in enumerate(entries, start=1):
            if item.slide_id == after_slide_id:
                insert_at = index
                break
        else:
            raise ValueError(f"unknown after_slide_id {after_slide_id!r}")
    elif after_slide_number is not None:
        for index, item in enumerate(entries, start=1):
            if item.slide_number == after_slide_number:
                insert_at = index
                break
        else:
            raise ValueError(f"unknown after_slide_number {after_slide_number}")

    new_entry = _clone_entry(entry)
    if not new_entry.depends_on and insert_at > 0 and new_entry.slide_role.value != "section-divider":
        new_entry.depends_on = [entries[insert_at - 1].slide_number]
    if new_entry.change_note is None:
        new_entry.change_note = "Inserted through large-deck orchestration."

    entries.insert(insert_at, new_entry)
    updated = renumber_slide_ledger(SlideLedger(deck_title=slide_ledger.deck_title, entries=entries, continuity_notes=slide_ledger.continuity_notes))
    if not any("insertions" in note.lower() for note in updated.continuity_notes):
        updated.continuity_notes.append("Track insertions, deletions, and renumbering in the slide ledger before continuing batch work.")
    return updated


def delete_slide_entry(
    slide_ledger: SlideLedger,
    *,
    slide_id: str | None = None,
    slide_number: int | None = None,
) -> SlideLedger:
    if slide_id is None and slide_number is None:
        raise ValueError("provide slide_id or slide_number")
    entries = [_clone_entry(item) for item in slide_ledger.entries]
    filtered = [
        entry
        for entry in entries
        if not ((slide_id is not None and entry.slide_id == slide_id) or (slide_number is not None and entry.slide_number == slide_number))
    ]
    if len(filtered) == len(entries):
        raise ValueError("no slide ledger entry matched the deletion target")
    updated = renumber_slide_ledger(SlideLedger(deck_title=slide_ledger.deck_title, entries=filtered, continuity_notes=slide_ledger.continuity_notes))
    if not any("deletions" in note.lower() for note in updated.continuity_notes):
        updated.continuity_notes.append("Deletions must be resolved through the ledger so numbering, dependencies, and batch ranges stay authoritative.")
    return updated


def revise_context_lock_decision(
    context_lock: ContextLock,
    decision_key: str,
    new_value: str,
    rationale: str,
    *,
    affected_batches: list[str] | None = None,
) -> ContextLock:
    decisions = [ContextLockDecision.model_validate(item.model_dump(mode="json", exclude_none=True)) for item in context_lock.locked_decisions]
    # `continuity_guidance` is the operator-facing payload. `continuity_warnings`
    # remains only as a compatibility mirror derived from that canonical guidance.
    guidance, _continuity_warning_mirror = normalize_continuity_guidance_and_mirror(
        continuity_guidance=context_lock.continuity_guidance,
        continuity_warnings=context_lock.continuity_warnings,
    )
    guidance = _unique_strings(guidance)
    affected = affected_batches or []

    existing = next((decision for decision in decisions if decision.decision_key == decision_key), None)
    previous_value = existing.locked_value if existing is not None else None
    if existing is None:
        decisions.append(
            ContextLockDecision(
                decision_key=decision_key,
                locked_value=new_value,
                rationale=rationale,
                affected_batches=affected,
            )
        )
    else:
        existing.locked_value = new_value
        existing.rationale = rationale
        existing.affected_batches = affected
        existing.updated_at = datetime.now(UTC)

    if previous_value is not None and previous_value != new_value:
        guidance.append(
            f"Locked decision `{decision_key}` changed from `{previous_value}` to `{new_value}`; resync unfinished batches before continuation."
        )

    payload = context_lock.model_dump(mode="json", exclude_none=True)
    payload["locked_decisions"] = [decision.model_dump(mode="json", exclude_none=True) for decision in decisions]
    payload["continuity_guidance"], payload["continuity_warnings"] = _persisted_continuity_guidance_and_mirror(guidance)
    payload["updated_at"] = datetime.now(UTC)
    if decision_key == "approved_workflow":
        payload["approved_workflow"] = new_value
    if decision_key == "approved_visual_route":
        payload["approved_visual_route"] = new_value
    return ContextLock.model_validate(payload)


def _completed_ranges_from_batches(batches: list[BatchChunk]) -> list[SlideRange]:
    return [batch.slide_range for batch in batches if batch.status == StageStatus.COMPLETE]


def _build_context_lock(
    workflow_plan: WorkflowPlan,
    blueprint: Blueprint,
    design_system: DesignSystem,
    deck_constitution: DeckConstitution,
    batches: list[BatchChunk],
) -> ContextLock:
    locked_design_system = LockedDesignSystem(
        theme_name=design_system.theme_name,
        visual_route_id=design_system.visual_route_id,
        color_tokens=[token.token for token in design_system.color_tokens],
        typography_tokens=[token.token for token in design_system.typography_tokens],
        section_divider_style=design_system.section_divider_style,
        chart_rules=design_system.chart_rules,
        table_rules=design_system.table_rules,
        highlight_rules=design_system.highlight_rules,
    )
    continuity_guidance: list[str] = []
    if len(batches) > 1:
        continuity_guidance.append(f"Deck work is split across {len(batches)} batches; keep visual route, numbering, and terminology locked.")
    if blueprint.appendix_start is not None:
        continuity_guidance.append(f"Appendix begins at slide {blueprint.appendix_start}; do not let appendix edits leak into the main story.")
    continuity_guidance, continuity_warnings = _persisted_continuity_guidance_and_mirror(continuity_guidance)
    return ContextLock(
        deck_title=workflow_plan.deck_title,
        scale_mode=workflow_plan.scale_mode,
        approved_workflow=blueprint.chosen_workflow,
        approved_visual_route=blueprint.recommended_route,
        locked_design_system=locked_design_system,
        locked_terminology=list(deck_constitution.terminology_rules),
        title_rules=list(deck_constitution.title_rules),
        numbering_rules=list(deck_constitution.numbering_rules),
        section_divider_rules=list(deck_constitution.section_divider_rules),
        appendix_boundary_rule=deck_constitution.appendix_boundary_rule,
        locked_decisions=[
            ContextLockDecision(
                decision_key="approved_workflow",
                locked_value=blueprint.chosen_workflow,
                rationale="Keep workflow selection stable across all production batches.",
                affected_batches=[batch.batch_id for batch in batches],
            ),
            ContextLockDecision(
                decision_key="approved_visual_route",
                locked_value=blueprint.recommended_route,
                rationale="Preserve one approved visual route across the full deck unless it is explicitly revised.",
                affected_batches=[batch.batch_id for batch in batches],
            ),
            ContextLockDecision(
                decision_key="title_rules",
                locked_value=" | ".join(deck_constitution.title_rules),
                rationale="Title hierarchy must stay stable across batches.",
                affected_batches=[batch.batch_id for batch in batches],
            ),
            ContextLockDecision(
                decision_key="terminology_rules",
                locked_value=" | ".join(deck_constitution.terminology_rules),
                rationale="Terminology drift breaks continuity across long-deck continuation.",
                affected_batches=[batch.batch_id for batch in batches],
            ),
            ContextLockDecision(
                decision_key="numbering_rules",
                locked_value=" | ".join(deck_constitution.numbering_rules),
                rationale="Slide numbering and appendix boundaries must remain authoritative in the ledger.",
                affected_batches=[batch.batch_id for batch in batches],
            ),
        ],
        continuity_guidance=continuity_guidance,
        continuity_warnings=continuity_warnings,
    )


def _batch_status(index: int, completed_ranges: list[SlideRange]) -> StageStatus:
    if index == 0 and not completed_ranges:
        return StageStatus.IN_PROGRESS
    return StageStatus.DRAFT


def _build_batches(
    slide_ledger: SlideLedger,
    scale_mode: ScaleMode,
    batch_size_overrides: dict[str, int] | None = None,
) -> tuple[list[BatchChunk], SlideLedger]:
    entries = [_clone_entry(entry) for entry in slide_ledger.entries]
    batch_limit = _batch_size_for_scale(scale_mode, batch_size_overrides)
    raw_groups = _section_groups(entries)
    batches: list[BatchChunk] = []

    for group in raw_groups:
        section_entry = group[0]
        group_chunks = [group]
        if supports_multi_batch(scale_mode) and len(group) > batch_limit:
            group_chunks = [group[index : index + batch_limit] for index in range(0, len(group), batch_limit)]

        for chunk_index, chunk in enumerate(group_chunks, start=1):
            start = chunk[0].slide_number
            end = chunk[-1].slide_number
            batch_id = f"batch-{section_entry.section_id}"
            cluster_id = f"cluster-{section_entry.section_id}"
            title = section_entry.section
            if len(group_chunks) > 1:
                batch_id = f"{batch_id}-{chunk_index:02d}"
                cluster_id = f"{cluster_id}-{chunk_index:02d}"
                title = f"{section_entry.section} cluster {chunk_index}"
            batch = BatchChunk(
                batch_id=batch_id,
                title=title,
                batch_mode=BatchMode.CONTINUITY_SENSITIVE if supports_continuity_controls(scale_mode) else BatchMode.SEQUENTIAL,
                intent=BatchIntent.NARRATIVE,
                slide_range=SlideRange(start=start, end=end),
                reason="Batch by narrative section first; split only when slide volume exceeds the scale-specific batch size.",
                part_id=section_entry.part_id,
                section_id=section_entry.section_id,
                cluster_id=cluster_id,
                continuity_anchor=chunk[0].main_message,
                objective=f"Carry the {section_entry.section} narrative without breaking numbering, terminology, or visual route continuity.",
                locked_decision_keys=[
                    "approved_workflow",
                    "approved_visual_route",
                    "title_rules",
                    "terminology_rules",
                    "numbering_rules",
                ],
                continuity_inputs_needed=[
                    "Approved workflow and visual route",
                    "Locked terminology and title rules",
                    "Appendix boundary and numbering rules",
                ],
                assets_needed=_unique_strings([asset for item in chunk for asset in item.required_evidence_assets]),
                expected_output_scope=[
                    "Continuation-ready slide range",
                    "Synchronized slide-ledger and continuity state",
                ],
                status=StageStatus.DRAFT,
            )
            batches.append(batch)
            for entry in chunk:
                entry.batch_id = batch.batch_id
                entry.cluster_id = cluster_id

    completed_ranges: list[SlideRange] = []
    for index, batch in enumerate(batches):
        batch.status = _batch_status(index, completed_ranges)
    updated_ledger = renumber_slide_ledger(
        SlideLedger(
            deck_title=slide_ledger.deck_title,
            entries=entries,
            continuity_notes=slide_ledger.continuity_notes,
        )
    )
    return batches, updated_ledger


def _build_hierarchy(slide_ledger: SlideLedger, batches: list[BatchChunk]) -> list[DeckHierarchyNode]:
    if not slide_ledger.entries:
        return []
    nodes: list[DeckHierarchyNode] = []
    deck_range = SlideRange(start=slide_ledger.entries[0].slide_number, end=slide_ledger.entries[-1].slide_number)
    deck_node = DeckHierarchyNode(
        node_id="deck-root",
        level=DeckHierarchyLevel.DECK,
        title=slide_ledger.deck_title,
        slide_range=deck_range,
    )
    nodes.append(deck_node)

    part_groups: dict[str, list[SlideLedgerEntry]] = {}
    for entry in slide_ledger.entries:
        part_groups.setdefault(entry.part_id or "main-story", []).append(entry)

    for part_id, part_entries in part_groups.items():
        part_node_id = f"part-{part_id}"
        nodes.append(
            DeckHierarchyNode(
                node_id=part_node_id,
                level=DeckHierarchyLevel.PART,
                title=part_id.replace("-", " ").title(),
                slide_range=SlideRange(start=part_entries[0].slide_number, end=part_entries[-1].slide_number),
                deck_mode=part_entries[0].deck_mode,
                parent_id=deck_node.node_id,
            )
        )

    for group in _section_groups(slide_ledger.entries):
        entry = group[0]
        nodes.append(
            DeckHierarchyNode(
                node_id=f"section-{entry.section_id}",
                level=DeckHierarchyLevel.SECTION,
                title=entry.section,
                slide_range=SlideRange(start=group[0].slide_number, end=group[-1].slide_number),
                deck_mode=entry.deck_mode,
                parent_id=f"part-{entry.part_id}",
            )
        )

    for batch in batches:
        nodes.append(
            DeckHierarchyNode(
                node_id=batch.cluster_id or f"cluster-{batch.batch_id}",
                level=DeckHierarchyLevel.SLIDE_CLUSTER,
                title=batch.title or batch.batch_id,
                slide_range=batch.slide_range,
                deck_mode=DeckMode.APPENDIX if batch.part_id == "appendix" else DeckMode.MAIN_STORY,
                parent_id=f"section-{batch.section_id}" if batch.section_id else "deck-root",
                batch_id=batch.batch_id,
            )
        )

    for entry in slide_ledger.entries:
        nodes.append(
            DeckHierarchyNode(
                node_id=f"slide-{entry.slide_id}",
                level=DeckHierarchyLevel.SLIDE,
                title=entry.title,
                slide_range=SlideRange(start=entry.slide_number, end=entry.slide_number),
                deck_mode=entry.deck_mode,
                parent_id=entry.cluster_id or f"section-{entry.section_id}",
                batch_id=entry.batch_id,
            )
        )

    child_map: dict[str, list[str]] = {}
    for node in nodes:
        if node.parent_id is None:
            continue
        child_map.setdefault(node.parent_id, []).append(node.node_id)
    for node in nodes:
        node.child_ids = child_map.get(node.node_id, [])
    return nodes


def _continuity_guidance(
    workflow_plan: WorkflowPlan,
    blueprint: Blueprint,
    slide_ledger: SlideLedger,
    batches: list[BatchChunk],
    continuity_alerts: list[BatchBoundaryContinuityAlert],
) -> list[str]:
    # Operator-facing continuity guidance is derived from canonical `continuity_alerts`
    # plus ledger/appendix context. Policy-driving inputs remain structured-first.
    warnings = list(slide_ledger.continuity_notes)
    if supports_continuity_controls(workflow_plan.scale_mode):
        warnings.append("Preserve approved terminology, numbering, and design tokens across every batch continuation.")
    if supports_multi_batch(workflow_plan.scale_mode):
        warnings.append("Narrative boundaries drive batching; only split by raw page count after section boundaries are established.")
    if blueprint.appendix_start is not None:
        warnings.append(f"Appendix boundary remains locked at slide {blueprint.appendix_start}.")
    if len(batches) > 1:
        warnings.append(f"Unfinished work spans {len(batches)} batches; use the handoff packet instead of conversational memory.")
    warnings.extend(_boundary_alert_warnings(continuity_alerts))
    return _unique_strings(warnings)


def _persisted_continuity_guidance_and_mirror(guidance_lines: list[str]) -> tuple[list[str], list[str]]:
    # Persisted control artifacts keep `continuity_guidance` as the canonical
    # operator-facing payload and derive `continuity_warnings` from it as a
    # compatibility mirror only. Newly written state files still retain that
    # mirror because `context-lock.json`, `handoff-packet.json`,
    # `batch-manifest.json`, and `state-capsule.json` remain supported durable
    # outputs until downstream acknowledgement plus a versioned deprecation
    # path authorize an explicit persisted-artifact retirement slice. That
    # support boundary covers durable JSON field presence only; readers still
    # need `continuity_guidance` / `continuity_alerts` as canonical policy
    # inputs, and raw mirror-first JSON consumption is out of support. The
    # current versioned boundary is `persisted-control-artifacts/v1`, and it is
    # schema metadata only rather than a durable JSON write-shape bump. PR-7.8
    # also reviewed these four artifact families individually and still found
    # them coupled enough at the durable write boundary that no single family
    # is yet authorized for its own mirror-retirement slice. PR-7.9 narrows
    # `handoff-packet.json` as the first candidate family, and PR-7.10 confirms
    # that its named in-repo file readers already load through schema
    # normalization rather than treating `continuity_warnings` as canonical
    # policy input. PR-7.11 confirms the named handoff writers likewise operate
    # on the normalized model and simply persist the supported contract back
    # through `save_state_file(...)`, so the remaining blocker is not in-repo
    # writer semantics. PR-7.12 further freezes the handoff support boundary:
    # raw `continuity_warnings` field presence is still supported for durable
    # compatibility readers, while mirror-first or normalization-bypass raw
    # readers are out of support. PR-7.13 then freezes the reader-
    # acknowledgement boundary: no acknowledged in-repo handoff reader or
    # writer requires raw field presence, so PR-7.18 can execute the first
    # handoff-only writer demotion safely. PR-7.14 defines that replacement
    # boundary more concretely:
    # supported in-repo handoff readers/writers should consume normalized
    # `continuity_guidance` and `continuity_alerts` after
    # `load_state_file(...)` / before `save_state_file(...)`. PR-7.18 now omits
    # raw `continuity_warnings` from newly written `handoff-packet.json`, while
    # older handoff artifacts remain guidance-first load-compatible at the
    # schema boundary. The other persisted control-artifact families still keep
    # their compatibility mirror. PR-7.15 freezes the repo-outside
    # acknowledgement boundary more explicitly, and PR-7.16 adds the schema-boundary malformed-payload
    # preflight to that same rollout gate: guidance-only payloads, stale
    # mirrors, scalar malformed guidance, and mapping-shaped malformed guidance
    # must keep normalizing back onto the canonical guidance/mirror seam before
    # any handoff-only write-shape change is approved. PR-7.17 then makes the
    # handoff family support-boundary decision explicit: repo-outside
    # `handoff-packet.json` readers that rely on raw `continuity_warnings`
    # field presence are out of support, but the current writers still emit
    # that mirror temporarily until a separately approved handoff-only writer
    # demotion slice lands. PR-7.19 then rechecks the next artifact families
    # and keeps `batch-manifest.json` plus `context-lock.json`
    # non-separable-for-now: both still move through the same retained durable
    # contract across large-deck emission, compile/remediation/apply file
    # seams, and shared `save_state_file(...)` writes, so this helper remains
    # the single clarification point rather than authorizing family-specific
    # writer demotion. The other persisted control-artifact families keep
    # their earlier supported durable field-presence boundary for now.
    continuity_guidance, continuity_warning_mirror = normalize_continuity_guidance_and_mirror(
        continuity_guidance=guidance_lines
    )
    return _unique_strings(continuity_guidance), _unique_strings(continuity_warning_mirror)

def _next_recommended_range(batches: list[BatchChunk]) -> SlideRange | None:
    for batch in batches:
        if batch.status != StageStatus.COMPLETE:
            return batch.slide_range
    return None


def _default_file_pointers(pointer_root: str) -> list[StateFilePointer]:
    root = pointer_root.rstrip("/\\")
    return [
        StateFilePointer(schema_name="workflow_plan", path=f"{root}/{DEFAULT_STATE_FILENAMES['workflow_plan']}"),
        StateFilePointer(schema_name="blueprint", path=f"{root}/{DEFAULT_STATE_FILENAMES['blueprint']}"),
        StateFilePointer(schema_name="design_system", path=f"{root}/{DEFAULT_STATE_FILENAMES['design_system']}"),
        StateFilePointer(schema_name="deck_constitution", path=f"{root}/{DEFAULT_STATE_FILENAMES['deck_constitution']}"),
        StateFilePointer(schema_name="layout_library", path=f"{root}/{DEFAULT_STATE_FILENAMES['layout_library']}"),
        StateFilePointer(schema_name="slide_ledger", path=f"{root}/{DEFAULT_STATE_FILENAMES['slide_ledger']}"),
        StateFilePointer(schema_name="batch_manifest", path=f"{root}/{DEFAULT_STATE_FILENAMES['batch_manifest']}"),
        StateFilePointer(schema_name="context_lock", path=f"{root}/{DEFAULT_STATE_FILENAMES['context_lock']}"),
        StateFilePointer(schema_name="handoff_packet", path=f"{root}/{DEFAULT_STATE_FILENAMES['handoff_packet']}"),
        StateFilePointer(schema_name="state_capsule", path=f"{root}/{DEFAULT_STATE_FILENAMES['state_capsule']}"),
        StateFilePointer(schema_name="remediation_plan", path=f"{root}/{DEFAULT_STATE_FILENAMES['remediation_plan']}"),
    ]


def _owner_for_finding(finding: QAFinding) -> RemediationOwner:
    return SKILL_OWNER_MAP.get(finding.remediation_skill, RemediationOwner.UPSTREAM_CONTENT_STORY)


def _execution_plan_for_finding(
    finding: QAFinding,
    scope: RemediationScope,
    owner: RemediationOwner,
    disposition: RemediationDisposition,
) -> tuple[RemediationExecutionAction, list[str]]:
    if disposition == RemediationDisposition.SAFE_TO_DEFER:
        return RemediationExecutionAction.MARK_DEFERRED, []
    if owner == RemediationOwner.UPSTREAM_CONTENT_STORY:
        return RemediationExecutionAction.MARK_REQUIRES_UPSTREAM_CHANGE, []
    if owner == RemediationOwner.QA_THRESHOLD_POLICY:
        if finding.blocking:
            return RemediationExecutionAction.MARK_BLOCKED, []
        return RemediationExecutionAction.MARK_DEFERRED, []
    if owner == RemediationOwner.STRUCTURED_VISUAL:
        if scope == RemediationScope.LOCAL_CHANGE_ONLY and finding.recommendation_type in {
            QARecommendationType.NEEDS_FALLBACK_ROUTE,
            QARecommendationType.NEEDS_LAYOUT_ADJUSTMENT,
            QARecommendationType.NEEDS_ASSET_REGENERATION,
        }:
            return RemediationExecutionAction.PROMOTE_SIMPLIFIED_STRUCTURED_VISUAL, [
                "compile-pptx",
                "qa-deck",
                "orchestrate-large-deck",
            ]
        if scope == RemediationScope.LOCAL_CHANGE_ONLY and finding.category in {"clarity", "density", "visual-fit", "chart-clarity", "table-clarity"}:
            return RemediationExecutionAction.DROP_BLOCKED_DENSE_VISUAL, [
                "compile-pptx",
                "qa-deck",
                "orchestrate-large-deck",
            ]
        return RemediationExecutionAction.MARK_BLOCKED if disposition in {
            RemediationDisposition.BLOCK_SHIP,
            RemediationDisposition.TRIGGER_REBUILD,
        } else RemediationExecutionAction.MARK_REQUIRES_UPSTREAM_CHANGE, []
    if owner == RemediationOwner.CROP_SOURCE_ASSET:
        if scope == RemediationScope.LOCAL_CHANGE_ONLY and finding.recommendation_type == QARecommendationType.NEEDS_FALLBACK_ROUTE:
            return RemediationExecutionAction.APPLY_KNOWN_FALLBACK, [
                "compile-pptx",
                "qa-deck",
                "orchestrate-large-deck",
            ]
        return RemediationExecutionAction.MARK_BLOCKED if disposition in {
            RemediationDisposition.BLOCK_SHIP,
            RemediationDisposition.TRIGGER_REBUILD,
        } else RemediationExecutionAction.MARK_DEFERRED, []
    if owner == RemediationOwner.COMPILER_LAYOUT:
        if scope == RemediationScope.LOCAL_CHANGE_ONLY and finding.category in {"asset-link", "layout", "build"}:
            refresh = ["qa-deck", "orchestrate-large-deck"]
            if finding.category == "build":
                refresh = ["compile-pptx", "qa-deck", "orchestrate-large-deck"]
            return RemediationExecutionAction.SYNC_STATUS_ONLY, refresh
        return RemediationExecutionAction.MARK_BLOCKED if disposition in {
            RemediationDisposition.BLOCK_SHIP,
            RemediationDisposition.TRIGGER_REBUILD,
        } else RemediationExecutionAction.MARK_REQUIRES_UPSTREAM_CHANGE, []
    return RemediationExecutionAction.MARK_REQUIRES_UPSTREAM_CHANGE, []


def _scope_for_finding(finding: QAFinding, slide_ledger: SlideLedger) -> RemediationScope:
    slide_range = _range_for_finding(finding)
    if finding.qa_layer == QALayer.OBJECT and finding.category in {"build", "numbering"}:
        return RemediationScope.DECK_LEVEL_REFLOW
    entries = _entries_in_range(slide_ledger, slide_range)
    if not entries:
        return RemediationScope.DECK_LEVEL_REFLOW if finding.qa_layer == QALayer.DECK else RemediationScope.LOCAL_CHANGE_ONLY
    sections = {entry.section_id for entry in entries}
    if finding.qa_layer == QALayer.DECK:
        if finding.category in {"terminology", "title-style", "section-drift", "design-drift"} and len(sections) <= 1:
            return RemediationScope.SECTION_LEVEL_REFLOW
        if len(entries) > 1 or len(sections) > 1:
            return RemediationScope.DECK_LEVEL_REFLOW
    if slide_range.start != slide_range.end:
        return RemediationScope.SECTION_LEVEL_REFLOW if len(sections) <= 1 else RemediationScope.DECK_LEVEL_REFLOW
    return RemediationScope.LOCAL_CHANGE_ONLY


def _disposition_for_finding(
    finding: QAFinding,
    scope: RemediationScope,
    owner: RemediationOwner,
) -> RemediationDisposition:
    if finding.recommendation_type == QARecommendationType.SAFE_TO_DEFER and not finding.blocking:
        return RemediationDisposition.SAFE_TO_DEFER
    if owner == RemediationOwner.COMPILER_LAYOUT and finding.category in {"build", "numbering"}:
        return RemediationDisposition.TRIGGER_REBUILD if finding.severity == QASeverity.CRITICAL else RemediationDisposition.FIX_BATCH_REQUIRED
    if finding.blocking or finding.severity == QASeverity.CRITICAL:
        return RemediationDisposition.BLOCK_SHIP
    if scope != RemediationScope.LOCAL_CHANGE_ONLY or finding.severity == QASeverity.MAJOR:
        return RemediationDisposition.FIX_BATCH_REQUIRED
    return RemediationDisposition.FIX_BATCH_REQUIRED


def _next_action_for_finding(
    finding: QAFinding,
    scope: RemediationScope,
    owner: RemediationOwner,
    slide_range: SlideRange,
) -> str:
    scope_label = slide_range.label()
    if owner == RemediationOwner.UPSTREAM_CONTENT_STORY:
        if scope == RemediationScope.LOCAL_CHANGE_ONLY:
            return f"Revise the approved title/message for slide {scope_label}, then refresh compile and QA for that slide."
        return f"Revise the approved story or terminology across slides {scope_label}, then rerun compile and QA for the affected range."
    if owner == RemediationOwner.CROP_SOURCE_ASSET:
        return f"Reopen source-asset handling for slides {scope_label}, preserve the fallback ladder, then refresh compile and QA."
    if owner == RemediationOwner.STRUCTURED_VISUAL:
        return f"Re-render the structured visual or promote the recorded fallback for slides {scope_label}, then refresh compile and QA."
    if owner == RemediationOwner.COMPILER_LAYOUT:
        return f"Adjust the layout/compiler mapping for slides {scope_label}, recompile the affected scope, and rerun QA."
    return f"Review the QA threshold or policy recorded for slides {scope_label} and capture an explicit waiver or rule update before the next QA round."


def _status_for_batch(
    batch: BatchChunk,
    slide_ledger: SlideLedger,
    action_ids: set[str],
    blocking_action_ids: set[str],
    has_build_context: bool,
    *,
    qa_slide_results_by_id: dict[str, QASlideResult] | None = None,
    qa_slide_results_by_number: dict[int, QASlideResult] | None = None,
) -> StageStatus:
    qa_slide_results_by_id = qa_slide_results_by_id or {}
    qa_slide_results_by_number = qa_slide_results_by_number or {}
    if action_ids:
        return StageStatus.BLOCKED if blocking_action_ids else StageStatus.READY
    if not has_build_context:
        return batch.status
    entries = _entries_in_range(slide_ledger, batch.slide_range)
    if not entries:
        return StageStatus.DRAFT
    if any(entry.compile_status != StageStatus.COMPLETE for entry in entries):
        return StageStatus.IN_PROGRESS
    resolved_entry_qa_statuses = [
        _resolve_entry_qa_status(
            entry,
            qa_slide_results_by_id,
            qa_slide_results_by_number,
        )[0]
        for entry in entries
    ]
    if any(status == QAStatus.FAIL for status in resolved_entry_qa_statuses):
        return StageStatus.BLOCKED
    if any(status == QAStatus.CONDITIONAL_PASS for status in resolved_entry_qa_statuses):
        return StageStatus.READY
    return StageStatus.COMPLETE


def _empty_remediation_plan(deck_title: str, scale_mode: ScaleMode, report_id: str | None = None) -> RemediationPlan:
    return RemediationPlan(
        plan_id=f"remediation-{_slug(deck_title)}",
        deck_title=deck_title,
        generated_from_report_id=report_id or "qa-unavailable",
        qa_status=QAStatus.PASS if report_id is None else QAStatus.CONDITIONAL_PASS,
        scale_mode=scale_mode,
        safe_to_ship_with_deferrals=True,
    )


def _plan_remediation(
    qa_report: QAReport | None,
    slide_ledger: SlideLedger,
    batches: list[BatchChunk],
    scale_mode: ScaleMode,
) -> tuple[RemediationPlan, list[BatchChunk]]:
    if qa_report is None:
        return _empty_remediation_plan(slide_ledger.deck_title, scale_mode), batches
    qa_policy_summary, _ = _resolve_qa_policy_summary(qa_report)
    qa_slide_results_by_id, qa_slide_results_by_number = _build_qa_slide_result_lookups(qa_report)
    resolved_qa_status = (
        qa_policy_summary.qa_status
        if qa_policy_summary is not None
        else qa_report.qa_status
    )

    actions: list[RemediationAction] = []
    actions_by_batch: dict[str, list[RemediationAction]] = {}
    global_actions: list[RemediationAction] = []

    for index, finding in enumerate(qa_report.findings, start=1):
        if finding.status != FindingStatus.OPEN:
            continue
        slide_range = _range_for_finding(finding)
        owner = _owner_for_finding(finding)
        scope = _scope_for_finding(finding, slide_ledger)
        disposition = _disposition_for_finding(finding, scope, owner)
        execution_action, rerun_stages = _execution_plan_for_finding(finding, scope, owner, disposition)
        target_batch = _batch_for_range(batches, slide_range)
        target_batch_id = target_batch.batch_id if target_batch is not None else None
        if scope == RemediationScope.DECK_LEVEL_REFLOW and (target_batch is None or slide_range.end - slide_range.start >= 2):
            target_batch_id = "batch-remediation-global"
        action = RemediationAction(
            action_id=f"remediate-{index:03d}",
            finding_id=finding.finding_id,
            severity=finding.severity,
            qa_layer=finding.qa_layer,
            category=finding.category,
            scope=scope,
            owner=owner,
            disposition=disposition,
            target_skill=finding.remediation_skill,
            next_action=_next_action_for_finding(finding, scope, owner, slide_range),
            rationale=finding.recommendation,
            blocking=finding.blocking or disposition in {RemediationDisposition.BLOCK_SHIP, RemediationDisposition.TRIGGER_REBUILD},
            execution_action=execution_action,
            rerun_stages=rerun_stages,
            slide_number=finding.slide_number,
            slide_id=finding.slide_id,
            slide_range=slide_range,
            target_batch_id=target_batch_id,
            tags=list(finding.tags),
        )
        actions.append(action)
        if target_batch_id == "batch-remediation-global":
            global_actions.append(action)
        elif target_batch_id is not None:
            actions_by_batch.setdefault(target_batch_id, []).append(action)

    updated_batches = [BatchChunk.model_validate(batch.model_dump(mode="json", exclude_none=True)) for batch in batches]
    batch_lookup = {batch.batch_id: batch for batch in updated_batches}
    remediation_batches: list[RemediationBatch] = []

    for batch in updated_batches:
        batch_actions = actions_by_batch.get(batch.batch_id, [])
        batch.remediation_finding_ids = [action.finding_id for action in batch_actions]
        batch.remediation_notes = [action.next_action for action in batch_actions]
        if batch_actions:
            batch.intent = BatchIntent.HYBRID
            batch.objective = f"{batch.objective or batch.title or batch.batch_id} Resolve the linked QA findings before the next compile/QA cycle."
            batch.risks = _unique_strings(batch.risks + [action.rationale for action in batch_actions])
            batch.expected_output_scope = _unique_strings(batch.expected_output_scope + ["Bounded remediation plan for linked findings"])
            remediation_batches.append(
                RemediationBatch(
                    batch_id=batch.batch_id,
                    title=batch.title or batch.batch_id,
                    intent=batch.intent,
                    slide_range=batch.slide_range,
                    objective=batch.objective or batch.batch_id,
                    finding_ids=batch.remediation_finding_ids,
                    owner_scopes=_unique_strings([action.owner.value for action in batch_actions]),
                    dependencies=list(batch.dependencies),
                    blocking=any(action.blocking for action in batch_actions),
                    expected_output_scope=list(batch.expected_output_scope),
                    rationale="Narrative batch also carries actionable QA findings for the same section scope.",
                )
            )

    if global_actions:
        global_batch = BatchChunk(
            batch_id="batch-remediation-global",
            title="Global QA remediation",
            batch_mode=BatchMode.CONTINUITY_SENSITIVE,
            intent=BatchIntent.QA_REMEDIATION,
            slide_range=SlideRange(start=slide_ledger.entries[0].slide_number, end=slide_ledger.entries[-1].slide_number),
            reason="Create one coordinated fix batch when QA findings cut across narrative sections or require a rebuild decision.",
            continuity_anchor="Preserve whole-deck continuity while resolving cross-cutting QA findings.",
            objective="Resolve cross-section continuity or build findings before the next ship decision.",
            dependencies=[batch.batch_id for batch in updated_batches if batch.intent != BatchIntent.QA_REMEDIATION],
            locked_decision_keys=["approved_workflow", "approved_visual_route", "title_rules", "terminology_rules", "numbering_rules"],
            continuity_inputs_needed=[
                "Current build manifest and slide-build-linkage",
                "Current QA report and blocking findings",
                "Locked numbering, terminology, and appendix boundary rules",
            ],
            assets_needed=[],
            risks=[action.rationale for action in global_actions],
            expected_output_scope=[
                "Bounded remediation pass plan",
                "Updated compile and QA refresh scope after fixes are applied",
            ],
            remediation_finding_ids=[action.finding_id for action in global_actions],
            remediation_notes=[action.next_action for action in global_actions],
            status=StageStatus.BLOCKED if any(action.blocking for action in global_actions) else StageStatus.READY,
        )
        updated_batches.append(global_batch)
        batch_lookup[global_batch.batch_id] = global_batch
        remediation_batches.append(
            RemediationBatch(
                batch_id=global_batch.batch_id,
                title=global_batch.title or global_batch.batch_id,
                intent=global_batch.intent,
                slide_range=global_batch.slide_range,
                objective=global_batch.objective or global_batch.batch_id,
                finding_ids=global_batch.remediation_finding_ids,
                owner_scopes=_unique_strings([action.owner.value for action in global_actions]),
                dependencies=list(global_batch.dependencies),
                blocking=any(action.blocking for action in global_actions),
                expected_output_scope=list(global_batch.expected_output_scope),
                rationale="These findings cross batch boundaries or require a coordinated rebuild decision.",
            )
        )

    action_ids_by_batch = {batch.batch_id: set(batch.remediation_finding_ids) for batch in updated_batches}
    blocking_ids_by_batch = {
        batch.batch_id: {action.finding_id for action in actions if action.target_batch_id == batch.batch_id and action.blocking}
        for batch in updated_batches
    }
    for batch in updated_batches:
        batch.status = _status_for_batch(
            batch,
            slide_ledger,
            action_ids_by_batch.get(batch.batch_id, set()),
            blocking_ids_by_batch.get(batch.batch_id, set()),
            has_build_context=True,
            qa_slide_results_by_id=qa_slide_results_by_id,
            qa_slide_results_by_number=qa_slide_results_by_number,
        )

    owner_counts: dict[str, int] = {}
    disposition_counts: dict[str, int] = {}
    for action in actions:
        owner_counts[action.owner.value] = owner_counts.get(action.owner.value, 0) + 1
        disposition_counts[action.disposition.value] = disposition_counts.get(action.disposition.value, 0) + 1

    deferred_ids = [action.finding_id for action in actions if action.disposition == RemediationDisposition.SAFE_TO_DEFER]
    blocking_ids = [action.finding_id for action in actions if action.blocking]
    next_batch = next(
        (
            batch.batch_id
            for batch in updated_batches
            if batch.status in {StageStatus.BLOCKED, StageStatus.READY} and batch.remediation_finding_ids
        ),
        None,
    )
    plan = RemediationPlan(
        plan_id=f"remediation-{_slug(slide_ledger.deck_title)}",
        deck_title=slide_ledger.deck_title,
        generated_from_report_id=qa_report.report_id,
        qa_status=resolved_qa_status,
        scale_mode=scale_mode,
        ship_blocked=bool(blocking_ids),
        safe_to_ship_with_deferrals=not blocking_ids and all(
            action.disposition == RemediationDisposition.SAFE_TO_DEFER for action in actions
        ),
        next_recommended_batch_id=next_batch,
        summary={
            "actionable_count": len(actions),
            "blocking_count": len(blocking_ids),
            "deferred_count": len(deferred_ids),
            "local_change_count": sum(1 for action in actions if action.scope == RemediationScope.LOCAL_CHANGE_ONLY),
            "section_reflow_count": sum(1 for action in actions if action.scope == RemediationScope.SECTION_LEVEL_REFLOW),
            "deck_reflow_count": sum(1 for action in actions if action.scope == RemediationScope.DECK_LEVEL_REFLOW),
            "owner_counts": owner_counts,
            "disposition_counts": disposition_counts,
        },
        actions=actions,
        fix_batches=remediation_batches,
        deferred_finding_ids=deferred_ids,
        blocking_finding_ids=blocking_ids,
    )
    return plan, updated_batches


def _sync_remediation_to_ledger(
    slide_ledger: SlideLedger,
    slide_build_linkage: SlideBuildLinkage | None,
    remediation_plan: RemediationPlan,
    batch_lookup: dict[str, BatchChunk],
) -> tuple[SlideLedger, SlideBuildLinkage | None]:
    actions_by_slide: dict[int, list[RemediationAction]] = {}
    for action in remediation_plan.actions:
        slide_range = action.slide_range if action.slide_range is not None else SlideRange(start=action.slide_number or 1, end=action.slide_number or 1)
        for entry in _entries_in_range(slide_ledger, slide_range):
            actions_by_slide.setdefault(entry.slide_number, []).append(action)

    updated_entries: list[SlideLedgerEntry] = []
    for entry in slide_ledger.entries:
        entry_actions = actions_by_slide.get(entry.slide_number, [])
        batch_ids = _unique_strings([action.target_batch_id for action in entry_actions if action.target_batch_id])
        status = None
        if entry_actions:
            status = StageStatus.BLOCKED if any(action.blocking for action in entry_actions) else StageStatus.READY
        updated_entries.append(
            entry.model_copy(
                update={
                    "remediation_status": status,
                    "remediation_finding_ids": [action.finding_id for action in entry_actions],
                    "remediation_batch_ids": batch_ids,
                    "batch_id": entry.batch_id or next((batch_id for batch_id in batch_ids if batch_id in batch_lookup), entry.batch_id),
                    "change_note": _unique_strings(
                        [entry.change_note or ""]
                        + [f"Continuation batch {entry.batch_id or batch_ids[0]}." for batch_id in batch_ids[:1]]
                        + [f"Remediation planned for {len(entry_actions)} finding(s)." if entry_actions else ""]
                    )[0]
                    if _unique_strings(
                        [entry.change_note or ""]
                        + [f"Continuation batch {entry.batch_id or batch_ids[0]}." for batch_id in batch_ids[:1]]
                        + [f"Remediation planned for {len(entry_actions)} finding(s)." if entry_actions else ""]
                    )
                    else entry.change_note,
                }
            )
        )

    updated_linkage = None
    if slide_build_linkage is not None:
        updated_slides = []
        for slide in slide_build_linkage.slides:
            slide_actions = actions_by_slide.get(slide.slide_number, [])
            batch_ids = _unique_strings([action.target_batch_id for action in slide_actions if action.target_batch_id])
            updated_slides.append(
                slide.model_copy(
                    update={
                        "batch_id": next((entry.batch_id for entry in updated_entries if entry.slide_number == slide.slide_number), getattr(slide, "batch_id", None)),
                        "remediation_status": StageStatus.BLOCKED if any(action.blocking for action in slide_actions) else StageStatus.READY if slide_actions else None,
                        "remediation_finding_ids": [action.finding_id for action in slide_actions],
                        "remediation_batch_ids": batch_ids,
                        "continuation_notes": [action.next_action for action in slide_actions[:2]],
                    }
                )
            )
        updated_linkage = SlideBuildLinkage(
            deck_title=slide_build_linkage.deck_title,
            pptx_path=slide_build_linkage.pptx_path,
            slides=updated_slides,
        )

    return (
        SlideLedger(
            deck_title=slide_ledger.deck_title,
            entries=updated_entries,
            continuity_notes=_unique_strings(slide_ledger.continuity_notes + [batch.reason for batch in batch_lookup.values() if batch.intent != BatchIntent.NARRATIVE]),
        ),
        updated_linkage,
    )


def orchestrate_large_deck(
    workflow_plan: WorkflowPlan,
    blueprint: Blueprint,
    design_system: DesignSystem,
    deck_constitution: DeckConstitution,
    layout_library: LayoutLibrary,
    slide_ledger: SlideLedger,
    *,
    build_manifest: BuildManifest | None = None,
    slide_build_linkage: SlideBuildLinkage | None = None,
    qa_report: QAReport | None = None,
    pointer_root: str = "state",
    canonical_state_root: str | None = None,
    batch_size_overrides: dict[str, int] | None = None,
) -> LargeDeckOutputs:
    del layout_library
    resolved_scale_mode = _infer_scale_mode(workflow_plan, slide_ledger, build_manifest, qa_report)
    effective_plan = workflow_plan.model_copy(update={"scale_mode": resolved_scale_mode})
    batches, updated_ledger = _build_batches(slide_ledger, resolved_scale_mode, batch_size_overrides)
    remediation_plan, batches = _plan_remediation(qa_report, updated_ledger, batches, resolved_scale_mode)
    batch_lookup = {batch.batch_id: batch for batch in batches}
    updated_ledger, updated_linkage = _sync_remediation_to_ledger(updated_ledger, slide_build_linkage, remediation_plan, batch_lookup)
    hierarchy = _build_hierarchy(updated_ledger, batches)
    total_planned_range = SlideRange(start=1, end=len(updated_ledger.entries))
    completed_ranges = [batch.slide_range for batch in batches if batch.status == StageStatus.COMPLETE]
    continuity_alerts = _continuity_alerts(updated_ledger, batches, qa_report)
    continuity_guidance = _continuity_guidance(effective_plan, blueprint, updated_ledger, batches, continuity_alerts)
    continuity_guidance, continuity_warnings = _persisted_continuity_guidance_and_mirror(continuity_guidance)
    context_lock = _build_context_lock(effective_plan, blueprint, design_system, deck_constitution, batches)
    current_batch = next((batch for batch in batches if batch.status in {StageStatus.BLOCKED, StageStatus.READY, StageStatus.IN_PROGRESS, StageStatus.DRAFT}), None)
    next_range = current_batch.slide_range if current_batch is not None else None
    next_batch_id = current_batch.batch_id if current_batch is not None else remediation_plan.next_recommended_batch_id
    unresolved_risks = _unique_strings([risk for batch in batches for risk in batch.risks if batch.status in {StageStatus.BLOCKED, StageStatus.READY}])
    qa_blockers = [action.next_action for action in remediation_plan.actions if action.blocking]
    has_production_context = (
        build_manifest is not None
        or slide_build_linkage is not None
        or qa_report is not None
        or any(entry.compile_status != StageStatus.DRAFT for entry in updated_ledger.entries)
        or _has_batch_local_qa_signal(updated_ledger, qa_report)
    )
    blueprint_approved = blueprint.approval_status == StageStatus.APPROVED or has_production_context
    active_gate = WorkflowGate.PRODUCTION_AND_QA if has_production_context else WorkflowGate.BLUEPRINT_AND_VISUAL_APPROVAL
    context_lock = context_lock.model_copy(
        update={
            "scale_mode": resolved_scale_mode,
            "active_numbering_range": next_range if next_range is not None else total_planned_range,
            "active_section_ids": _unique_strings([current_batch.section_id] if current_batch is not None and current_batch.section_id else []),
            "active_cluster_ids": _unique_strings([current_batch.cluster_id] if current_batch is not None and current_batch.cluster_id else []),
            "unresolved_risks": unresolved_risks,
            "qa_blockers": qa_blockers,
            "continuity_guidance": continuity_guidance,
            "continuity_warnings": continuity_warnings,
            "continuity_alerts": continuity_alerts,
        }
    )
    next_handoff_range = None
    if current_batch is not None:
        next_handoff_range = next(
            (
                batch.slide_range
                for batch in batches
                if batch.slide_range.start > current_batch.slide_range.end and batch.status != StageStatus.COMPLETE
            ),
            None,
        )

    batch_manifest = BatchManifest(
        deck_title=workflow_plan.deck_title,
        scale_mode=resolved_scale_mode,
        batch_mode=BatchMode.CONTINUITY_SENSITIVE if supports_continuity_controls(resolved_scale_mode) else BatchMode.SEQUENTIAL,
        hierarchy=hierarchy,
        batches=batches,
        completed_ranges=completed_ranges,
        total_planned_range=total_planned_range,
        next_recommended_range=next_range,
        continuity_guidance=continuity_guidance,
        continuity_warnings=continuity_warnings,
        continuity_alerts=continuity_alerts,
    )

    produced_artifacts = []
    reviewed_artifacts = []
    if build_manifest is not None:
        produced_artifacts.extend([build_manifest.pptx_path, build_manifest.linkage_path])
    if qa_report is not None:
        reviewed_artifacts.extend(qa_report.checked_artifacts or [qa_report.audited_scope])

    handoff_packet = HandoffPacket(
        packet_id=f"handoff-{_slug(workflow_plan.deck_title)}",
        deck_title=workflow_plan.deck_title,
        batch_id=current_batch.batch_id if current_batch is not None else "batch-complete",
        slide_range=current_batch.slide_range if current_batch is not None else total_planned_range,
        completed_ranges=completed_ranges,
        total_planned_range=total_planned_range,
        next_recommended_range=next_handoff_range,
        approved_workflow=blueprint.chosen_workflow,
        approved_visual_route=blueprint.recommended_route,
        file_pointers=_default_file_pointers(pointer_root),
        produced_artifacts=_unique_strings(produced_artifacts),
        reviewed_artifacts=_unique_strings(reviewed_artifacts),
        open_issues=[action.rationale for action in remediation_plan.actions if action.disposition != RemediationDisposition.SAFE_TO_DEFER],
        continuity_guidance=continuity_guidance,
        continuity_warnings=continuity_warnings,
        continuity_alerts=continuity_alerts,
        continuity_sensitive_decisions=[decision.decision_key for decision in context_lock.locked_decisions],
        numbering_updates=["No numbering changes are approved until the slide ledger is revised."] if current_batch is not None else ["Deck numbering is currently stable across the compiled build."],
        assets_still_needed=[action.next_action for action in remediation_plan.actions if action.owner in {RemediationOwner.CROP_SOURCE_ASSET, RemediationOwner.STRUCTURED_VISUAL}],
        verification_items_open=[action.next_action for action in remediation_plan.actions if action.blocking],
        handoff_instructions=[
            "Use the context lock as the source of truth for workflow, visual route, title rules, terminology, and numbering.",
            "Continue only inside the recommended batch id or explicitly revise the batch manifest first.",
            "Do not apply fixes outside the bounded remediation plan without refreshing the ledger and QA state.",
        ],
        next_recommended_batch_id=next_batch_id,
    )

    state_capsule = StateCapsule(
        capsule_id=f"capsule-{_slug(workflow_plan.deck_title)}",
        deck_title=workflow_plan.deck_title,
        active_gate=active_gate,
        deck_mode=workflow_plan.deck_mode,
        scale_mode=resolved_scale_mode,
        blueprint_approved=blueprint_approved,
        approved_workflow=blueprint.chosen_workflow,
        approved_visual_route=blueprint.recommended_route,
        locked_design_system=context_lock.locked_design_system,
        locked_design_summary=[
            f"Theme: {context_lock.locked_design_system.theme_name}",
            f"Visual route: {context_lock.locked_design_system.visual_route_id}",
            f"Color tokens: {', '.join(context_lock.locked_design_system.color_tokens)}",
        ],
        completed_ranges=completed_ranges,
        total_planned_range=total_planned_range,
        next_recommended_range=next_range,
        completed_batch_ids=[batch.batch_id for batch in batches if batch.status == StageStatus.COMPLETE],
        current_batch_id=current_batch.batch_id if current_batch is not None else None,
        next_recommended_batch_id=next_batch_id,
        open_issues=list(handoff_packet.open_issues),
        continuity_guidance=continuity_guidance,
        continuity_warnings=continuity_warnings,
        continuity_alerts=continuity_alerts,
        file_pointers=_default_file_pointers(pointer_root),
        pending_actions=[action.next_action for action in remediation_plan.actions if action.disposition != RemediationDisposition.SAFE_TO_DEFER] or ["No active remediation actions remain."],
        remediation_backlog_count=len(remediation_plan.actions),
        canonical_state_root=canonical_state_root or pointer_root,
        qa_round=qa_report.bounded_round if qa_report is not None else 0,
        max_qa_rounds=qa_report.max_rounds if qa_report is not None else workflow_plan.bounded_qa_rounds,
    )

    return LargeDeckOutputs(
        batch_manifest=batch_manifest,
        context_lock=context_lock,
        handoff_packet=handoff_packet,
        state_capsule=state_capsule,
        remediation_plan=remediation_plan,
        slide_ledger=updated_ledger,
        slide_build_linkage=updated_linkage,
    )


def orchestrate_large_deck_from_files(
    workflow_plan_path: str | Path,
    blueprint_path: str | Path,
    design_system_path: str | Path,
    deck_constitution_path: str | Path,
    layout_library_path: str | Path,
    slide_ledger_path: str | Path,
    *,
    build_manifest_path: str | Path | None = None,
    slide_build_linkage_path: str | Path | None = None,
    qa_report_path: str | Path | None = None,
    pointer_root: str = "state",
    canonical_state_root: str | None = None,
    batch_size_overrides: dict[str, int] | None = None,
) -> LargeDeckOutputs:
    workflow_plan = load_state_file(workflow_plan_path)
    blueprint = load_state_file(blueprint_path)
    design_system = load_state_file(design_system_path)
    deck_constitution = load_state_file(deck_constitution_path)
    layout_library = load_state_file(layout_library_path)
    slide_ledger = load_state_file(slide_ledger_path)
    build_manifest = load_pptx_compile_file(build_manifest_path) if build_manifest_path is not None and Path(build_manifest_path).is_file() else None
    slide_build_linkage = load_pptx_compile_file(slide_build_linkage_path) if slide_build_linkage_path is not None and Path(slide_build_linkage_path).is_file() else None
    qa_report = load_state_file(qa_report_path) if qa_report_path is not None and Path(qa_report_path).is_file() else None

    if workflow_plan.schema_name != "workflow_plan":
        raise TypeError(f"expected workflow_plan, found {workflow_plan.schema_name}")
    if blueprint.schema_name != "blueprint":
        raise TypeError(f"expected blueprint, found {blueprint.schema_name}")
    if design_system.schema_name != "design_system":
        raise TypeError(f"expected design_system, found {design_system.schema_name}")
    if deck_constitution.schema_name != "deck_constitution":
        raise TypeError(f"expected deck_constitution, found {deck_constitution.schema_name}")
    if layout_library.schema_name != "layout_library":
        raise TypeError(f"expected layout_library, found {layout_library.schema_name}")
    if slide_ledger.schema_name != "slide_ledger":
        raise TypeError(f"expected slide_ledger, found {slide_ledger.schema_name}")
    if build_manifest is not None and build_manifest.schema_name != "build_manifest":
        raise TypeError(f"expected build_manifest, found {build_manifest.schema_name}")
    if slide_build_linkage is not None and slide_build_linkage.schema_name != "slide_build_linkage":
        raise TypeError(f"expected slide_build_linkage, found {slide_build_linkage.schema_name}")
    if qa_report is not None and qa_report.schema_name != "qa_report":
        raise TypeError(f"expected qa_report, found {qa_report.schema_name}")

    return orchestrate_large_deck(
        workflow_plan=workflow_plan,
        blueprint=blueprint,
        design_system=design_system,
        deck_constitution=deck_constitution,
        layout_library=layout_library,
        slide_ledger=slide_ledger,
        build_manifest=build_manifest,
        slide_build_linkage=slide_build_linkage,
        qa_report=qa_report,
        pointer_root=pointer_root,
        canonical_state_root=canonical_state_root,
        batch_size_overrides=batch_size_overrides,
    )


def write_large_deck_outputs(outputs: LargeDeckOutputs, output_dir: str | Path) -> dict[str, Path]:
    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    models = {
        "batch_manifest": outputs.batch_manifest,
        "context_lock": outputs.context_lock,
        "handoff_packet": outputs.handoff_packet,
        "state_capsule": outputs.state_capsule,
        "remediation_plan": outputs.remediation_plan,
        "slide_ledger": outputs.slide_ledger,
    }
    written: dict[str, Path] = {}
    for schema_name, model in models.items():
        path = resolved_output_dir / DEFAULT_STATE_FILENAMES[schema_name]
        save_state_file(model, path)
        written[schema_name] = path
    if outputs.slide_build_linkage is not None:
        written["slide_build_linkage"] = save_state_file(outputs.slide_build_linkage, resolved_output_dir / "slide-build-linkage.json")
    return written


