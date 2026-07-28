"""Phase 14 approved upstream-fix apply with minimal deterministic reruns."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .asset_derivation import derive_assets_from_blueprint
from ..compat.legacy_non_pptx import WorkflowGate
from .deck_qa import run_deck_qa
from .document_asset_crop import (
    load_document_crop_file,
    run_document_asset_crop,
    run_document_crop_review,
    write_document_crop_outputs,
)
from .large_deck_orchestration import orchestrate_large_deck
from ..pptx_compiler import BuildManifest, SlideBuildLinkage, compile_pptx, load_pptx_compile_file
from ..compat.legacy_non_pptx import (
    ApprovalDecisionStatus,
    ApprovalPacket,
    ApprovalPacketSet,
    ApplyDecisionStatus,
    ApprovedApplyDeltaResult,
    ApprovedApplyFixResult,
    ApprovedApplyReport,
    ApprovedApplySummary,
    AssetKind,
    AssetManifest,
    AssetRequest,
    AssetRequests,
    AuthoringDeltaRecord,
    AuthoringDeltas,
    BatchManifest,
    Blueprint,
    ContextLock,
    ContractModel,
    DEFAULT_STATE_FILENAMES,
    DeckConstitution,
    DeltaOperation,
    DeltaOptionSelection,
    DesignSystem,
    HandoffPacket,
    LayoutLibrary,
    PacketApprovalMode,
    QAGovernance,
    QAReport,
    RemediationExecutionReport,
    RemediationPlan,
    SlideLedger,
    SlideRange,
    StateCapsule,
    StateFilePointer,
    UpstreamArtifactName,
    UpstreamFixPlan,
    UpstreamFixProposal,
    VisualSourcePreference,
    VizManifest,
    VizSpecSet,
    load_state_file,
    save_state_file,
)
from .structured_visuals import run_structured_visuals, write_structured_visual_outputs
from .workflow_planner import WorkflowPlan


PIPELINE_RERUN_ORDER = [
    "derive-assets",
    "extract-assets",
    "review-crops",
    "render-visuals",
    "compile-pptx",
    "qa-deck",
    "orchestrate-large-deck",
]
SELECTOR_RE = re.compile(r"^(?P<collection>[A-Za-z_][A-Za-z0-9_]*)\[(?P<field>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.+)\]$")
PATH_SEGMENT_RE = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:\[(?P<index>\d+)\])?$")
ROOT_SELECTOR_VALUES = {"", "root", "$"}
MISSING = object()
BLUEPRINT_PHASE5_FIELDS = {"layout_pattern_id", "visual_type", "required_evidence_assets"}
VISUAL_CONSTITUTION_FIELDS = {
    "approved_visual_route",
    "design_token_refs",
    "layout_pattern_ids",
    "chart_rules",
    "table_rules",
    "screenshot_rules",
    "visual_consistency_rules",
}


class ApprovedApplyOutputs(ContractModel):
    approved_apply_report: ApprovedApplyReport
    blueprint: Blueprint
    design_system: DesignSystem
    deck_constitution: DeckConstitution
    layout_library: LayoutLibrary
    slide_ledger: SlideLedger
    asset_requests: AssetRequests | None = None
    viz_spec: VizSpecSet | None = None
    asset_manifest: AssetManifest
    viz_manifest: VizManifest
    build_manifest: BuildManifest
    qa_report: QAReport
    qa_governance: QAGovernance | None = None
    slide_build_linkage: SlideBuildLinkage
    batch_manifest: BatchManifest
    context_lock: ContextLock
    handoff_packet: HandoffPacket | None = None
    state_capsule: StateCapsule
    remediation_plan: RemediationPlan
    remediation_execution_report: RemediationExecutionReport
    upstream_fix_plan: UpstreamFixPlan
    approval_packet: ApprovalPacketSet
    authoring_deltas: AuthoringDeltas
    pptx_path: Path | None = None


@dataclass(slots=True)
class _DeltaPreview:
    before_value: Any
    after_value: Any
    changed: bool
    selected_option_id: str | None
    notes: list[str]


class _SkipDelta(RuntimeError):
    pass


class _BlockedDelta(RuntimeError):
    pass


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def _clone_payload(model) -> dict[str, Any]:
    return model.to_payload()


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


def _resolve_path(path_text: str | None, artifact_root: Path) -> Path | None:
    if not path_text:
        return None
    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate
    return (artifact_root / candidate).resolve()


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


def _ordered_reruns(stages: list[str]) -> list[str]:
    stage_set = set(stages)
    return [stage for stage in PIPELINE_RERUN_ORDER if stage in stage_set]


def _matches_selector(actual: Any, expected_text: str) -> bool:
    if isinstance(actual, bool):
        return ("true" if actual else "false") == expected_text.lower()
    if isinstance(actual, int) and expected_text.isdigit():
        return actual == int(expected_text)
    return str(actual) == expected_text


def _resolve_selector_node(payload: dict[str, Any], selector: str) -> dict[str, Any]:
    if selector in ROOT_SELECTOR_VALUES:
        return payload
    match = SELECTOR_RE.match(selector)
    if match is None:
        raise ValueError(f"unsupported selector {selector!r}")
    collection = match.group("collection")
    field = match.group("field")
    expected = match.group("value")
    items = payload.get(collection)
    if not isinstance(items, list):
        raise ValueError(f"selector collection {collection!r} is not a list")
    matches = [item for item in items if isinstance(item, dict) and _matches_selector(item.get(field), expected)]
    if len(matches) != 1:
        raise ValueError(f"selector {selector!r} must match exactly one item")
    return matches[0]


def _parse_field_path(field_path: str) -> list[tuple[str, int | None]]:
    segments: list[tuple[str, int | None]] = []
    for raw_segment in field_path.split("."):
        match = PATH_SEGMENT_RE.match(raw_segment)
        if match is None:
            raise ValueError(f"unsupported field_path segment {raw_segment!r}")
        index_text = match.group("index")
        segments.append((match.group("name"), int(index_text) if index_text is not None else None))
    return segments


def _read_field_value(node: dict[str, Any], field_path: str):
    current: Any = node
    for name, index in _parse_field_path(field_path):
        if not isinstance(current, dict) or name not in current:
            return MISSING
        current = current[name]
        if index is not None:
            if not isinstance(current, list) or index >= len(current):
                return MISSING
            current = current[index]
    return current


def _write_field_value(node: dict[str, Any], field_path: str, value: Any):
    current: Any = node
    segments = _parse_field_path(field_path)
    for name, index in segments[:-1]:
        if not isinstance(current, dict) or name not in current:
            raise ValueError(f"field_path {field_path!r} does not exist before the target leaf")
        current = current[name]
        if index is not None:
            if not isinstance(current, list) or index >= len(current):
                raise ValueError(f"field_path {field_path!r} does not exist before the target leaf")
            current = current[index]
    leaf_name, leaf_index = segments[-1]
    if not isinstance(current, dict):
        raise ValueError(f"field_path {field_path!r} does not resolve to a mutable object")
    if leaf_index is None:
        current[leaf_name] = value
        return
    bucket = current.get(leaf_name)
    if not isinstance(bucket, list) or leaf_index >= len(bucket):
        raise ValueError(f"field_path {field_path!r} does not resolve to a mutable list item")
    bucket[leaf_index] = value


def _remove_field_value(node: dict[str, Any], field_path: str):
    current: Any = node
    segments = _parse_field_path(field_path)
    for name, index in segments[:-1]:
        if not isinstance(current, dict) or name not in current:
            return
        current = current[name]
        if index is not None:
            if not isinstance(current, list) or index >= len(current):
                return
            current = current[index]
    leaf_name, leaf_index = segments[-1]
    if not isinstance(current, dict) or leaf_name not in current:
        return
    if leaf_index is None:
        current.pop(leaf_name, None)
        return
    bucket = current.get(leaf_name)
    if isinstance(bucket, list) and leaf_index < len(bucket):
        bucket.pop(leaf_index)


def _selection_map(
    approval_packet: ApprovalPacketSet,
    overrides: dict[str, str] | None,
) -> dict[str, str]:
    mapping = dict(overrides or {})
    for packet in approval_packet.packets:
        for selection in packet.selected_delta_options:
            mapping.setdefault(selection.delta_id, selection.option_id)
    return mapping


def _selected_option(delta: AuthoringDeltaRecord, selection_map: dict[str, str]) -> tuple[str | None, Any]:
    if delta.operation != DeltaOperation.CHOOSE_ONE:
        return None, delta.proposed_value
    option_id = selection_map.get(delta.delta_id) or delta.selected_option_id
    if option_id is None and len(delta.options) == 1:
        option_id = delta.options[0].option_id
    if option_id is None:
        raise _BlockedDelta(f"Delta {delta.delta_id} requires an explicit bounded option selection.")
    for option in delta.options:
        if option.option_id == option_id:
            return option_id, option.value
    raise _BlockedDelta(f"Selected option {option_id!r} does not exist on delta {delta.delta_id}.")


def _preview_delta(node: dict[str, Any], delta: AuthoringDeltaRecord, selection_map: dict[str, str]) -> _DeltaPreview:
    before_value = _read_field_value(node, delta.field_path)
    selected_option_id, desired_value = _selected_option(delta, selection_map)
    before_snapshot = None if before_value is MISSING else before_value

    if delta.operation == DeltaOperation.INSERT:
        if before_value in {MISSING, None}:
            _write_field_value(node, delta.field_path, desired_value)
            return _DeltaPreview(before_snapshot, desired_value, True, selected_option_id, [])
        if before_value == desired_value:
            return _DeltaPreview(
                before_snapshot,
                before_value,
                False,
                selected_option_id,
                ["Target field already matched the approved inserted value."],
            )
        raise _BlockedDelta(f"Insert delta {delta.delta_id} cannot overwrite an existing non-empty value.")

    if delta.operation == DeltaOperation.REMOVE:
        if before_value is MISSING:
            return _DeltaPreview(None, None, False, None, ["Target field was already absent."])
        if delta.current_value is not None and before_value != delta.current_value:
            raise ValueError(f"Current value mismatch for remove delta {delta.delta_id}.")
        _remove_field_value(node, delta.field_path)
        return _DeltaPreview(before_snapshot, None, True, None, [])

    if before_value is not MISSING and desired_value is not None and before_value == desired_value:
        return _DeltaPreview(
            before_snapshot,
            before_value,
            False,
            selected_option_id,
            ["Target field already matched the approved value."],
        )
    if delta.current_value is not None and before_value != delta.current_value:
        raise ValueError(f"Current value mismatch for delta {delta.delta_id}.")
    _write_field_value(node, delta.field_path, desired_value)
    return _DeltaPreview(before_snapshot, desired_value, True, selected_option_id, [])


def _artifact_model_map(
    *,
    blueprint: Blueprint,
    design_system: DesignSystem,
    deck_constitution: DeckConstitution,
    layout_library: LayoutLibrary,
    slide_ledger: SlideLedger,
    asset_requests: AssetRequests | None,
    viz_spec: VizSpecSet | None,
) -> dict[UpstreamArtifactName, object]:
    mapping: dict[UpstreamArtifactName, object] = {
        UpstreamArtifactName.BLUEPRINT: blueprint,
        UpstreamArtifactName.DESIGN_SYSTEM: design_system,
        UpstreamArtifactName.DECK_CONSTITUTION: deck_constitution,
        UpstreamArtifactName.LAYOUT_LIBRARY: layout_library,
        UpstreamArtifactName.SLIDE_LEDGER: slide_ledger,
    }
    if asset_requests is not None:
        mapping[UpstreamArtifactName.ASSET_REQUESTS] = asset_requests
    if viz_spec is not None:
        mapping[UpstreamArtifactName.VIZ_SPEC] = viz_spec
    return mapping


def _request_needs_crop_rerun(request: AssetRequest) -> bool:
    if request.asset_kind in {
        AssetKind.DOCUMENT_CROP,
        AssetKind.IMAGE,
        AssetKind.LOGO,
        AssetKind.ICON,
        AssetKind.REFERENCE,
    }:
        return True
    return request.visual_source_preference in {
        VisualSourcePreference.DOCUMENT_CROP,
        VisualSourcePreference.EXISTING_ASSET,
    }


def _request_for_selector(asset_requests: AssetRequests | None, selector: str) -> AssetRequest | None:
    if asset_requests is None:
        return None
    match = SELECTOR_RE.match(selector)
    if match is None or match.group("collection") != "requests":
        return None
    field = match.group("field")
    expected = match.group("value")
    for request in asset_requests.requests:
        if _matches_selector(getattr(request, field, None), expected):
            return request
    return None


def _needs_phase5_sync(delta: AuthoringDeltaRecord) -> bool:
    if delta.target_artifact in {
        UpstreamArtifactName.DESIGN_SYSTEM,
        UpstreamArtifactName.LAYOUT_LIBRARY,
    }:
        return True
    if delta.target_artifact == UpstreamArtifactName.DECK_CONSTITUTION:
        return delta.field_path in VISUAL_CONSTITUTION_FIELDS
    if delta.target_artifact != UpstreamArtifactName.BLUEPRINT:
        return False
    return delta.field_path in BLUEPRINT_PHASE5_FIELDS or delta.field_path.startswith("production_bridge.")


def _plan_fix_reruns(
    fix: UpstreamFixProposal,
    deltas: list[AuthoringDeltaRecord],
    *,
    asset_requests: AssetRequests | None,
) -> list[str]:
    stages: list[str] = []
    if any(_needs_phase5_sync(delta) for delta in deltas):
        stages.append("derive-assets")
    for delta in deltas:
        if delta.target_artifact == UpstreamArtifactName.ASSET_REQUESTS:
            request = _request_for_selector(asset_requests, delta.selector)
            if request is None or _request_needs_crop_rerun(request):
                stages.extend(["extract-assets", "review-crops"])
            else:
                stages.append("render-visuals")
        elif delta.target_artifact == UpstreamArtifactName.VIZ_SPEC:
            stages.append("render-visuals")
        elif delta.target_artifact == UpstreamArtifactName.DECK_CONSTITUTION:
            if delta.field_path not in VISUAL_CONSTITUTION_FIELDS:
                stages.extend(["compile-pptx", "qa-deck", "orchestrate-large-deck"])
        elif delta.target_artifact == UpstreamArtifactName.BLUEPRINT and not _needs_phase5_sync(delta):
            stages.extend(["compile-pptx", "qa-deck", "orchestrate-large-deck"])
        elif delta.target_artifact == UpstreamArtifactName.SLIDE_LEDGER:
            stages.extend(["compile-pptx", "qa-deck", "orchestrate-large-deck"])
    if "derive-assets" in stages:
        stages.extend(["compile-pptx", "qa-deck", "orchestrate-large-deck"])
    if "extract-assets" in stages or "review-crops" in stages or "render-visuals" in stages:
        stages.extend(["compile-pptx", "qa-deck", "orchestrate-large-deck"])
    if not stages:
        stages.extend(fix.downstream_rerun_stages)
    return _ordered_reruns(stages)


def _fix_to_packet_map(approval_packet: ApprovalPacketSet) -> dict[str, ApprovalPacket]:
    return {
        fix_id: packet
        for packet in approval_packet.packets
        for fix_id in packet.included_fix_ids
    }


def _canonical_state_root(state_capsule: StateCapsule, state_output_dir: Path, artifact_root: Path) -> str:
    if state_capsule.canonical_state_root:
        return state_capsule.canonical_state_root
    return _display_path(state_output_dir, artifact_root)


def _packet_status_from_fixes(
    packet: ApprovalPacket,
    *,
    fully_approved: bool,
    fix_statuses: dict[str, ApplyDecisionStatus],
) -> tuple[ApprovalDecisionStatus, ApplyDecisionStatus]:
    packet_fix_statuses = [fix_statuses.get(fix_id) for fix_id in packet.included_fix_ids if fix_id in fix_statuses]
    if packet_fix_statuses and all(status == ApplyDecisionStatus.APPLIED for status in packet_fix_statuses):
        return ApprovalDecisionStatus.APPROVED, ApplyDecisionStatus.APPLIED
    if fully_approved:
        for status in (
            ApplyDecisionStatus.FAILED,
            ApplyDecisionStatus.BLOCKED,
            ApplyDecisionStatus.DEFERRED,
            ApplyDecisionStatus.SKIPPED,
        ):
            if status in packet_fix_statuses:
                return ApprovalDecisionStatus.APPROVED, status
        return ApprovalDecisionStatus.APPROVED, packet.apply_status
    prior_apply = packet.apply_status if packet.apply_status != ApplyDecisionStatus.APPLIED else ApplyDecisionStatus.PENDING
    return packet.approval_status, prior_apply


def _update_state_capsule(
    state_capsule: StateCapsule,
    *,
    qa_report: QAReport,
    remediation_plan: RemediationPlan,
    pending_packet_ids: list[str],
    remaining_fix_ids: list[str],
    blocked_issue_ids: list[str],
    pointer_root: str,
    warnings: list[str],
) -> StateCapsule:
    file_pointers = list(state_capsule.file_pointers)
    for schema_name in ("approval_packet", "authoring_deltas", "upstream_fix_plan", "approved_apply_report"):
        file_pointers = _upsert_pointer(
            file_pointers,
            schema_name=schema_name,
            path=f"{pointer_root}/{DEFAULT_STATE_FILENAMES[schema_name]}",
        )
    pending_actions: list[str] = []
    pending_actions.extend(
        f"Review approval packet {packet_id} before running Phase 14 again."
        for packet_id in pending_packet_ids
    )
    pending_actions.extend(warnings)
    if blocked_issue_ids:
        pending_actions.append("Manual upstream architecture review is still required for blocked issues.")
    if not pending_actions:
        pending_actions = ["No pending upstream approval packets remain; continue with the refreshed remediation backlog."]
    open_issues = _dedupe(
        [finding.summary for finding in qa_report.findings if finding.status.value == "open"]
        + [f"Approval packet {packet_id} is still pending." for packet_id in pending_packet_ids]
        + [f"Blocked upstream issue {issue_id} still needs manual review." for issue_id in blocked_issue_ids]
    )
    return state_capsule.model_copy(
        update={
            "active_gate": WorkflowGate.PRODUCTION_AND_QA,
            "open_issues": open_issues,
            "pending_actions": _dedupe(pending_actions),
            "pending_approval_packet_ids": list(pending_packet_ids),
            "pending_upstream_fix_ids": list(remaining_fix_ids),
            "remediation_backlog_count": len(remediation_plan.actions),
            "file_pointers": file_pointers,
            "updated_at": datetime.now(UTC),
        }
    )


def _update_handoff_packet(
    handoff_packet: HandoffPacket | None,
    *,
    qa_report: QAReport,
    remediation_plan: RemediationPlan,
    pending_packet_ids: list[str],
    remaining_fix_ids: list[str],
    blocked_issue_ids: list[str],
    refreshed_artifacts: list[str],
    report_name: str,
) -> HandoffPacket | None:
    if handoff_packet is None:
        return None
    instructions = list(handoff_packet.handoff_instructions)
    if pending_packet_ids:
        instructions.append("Review the remaining approval packets before rerunning the approved-apply stage.")
    elif blocked_issue_ids:
        instructions.append("Narrow the remaining blocked deck-level issue before authoring another approval packet.")
    else:
        instructions.append("Continue with the refreshed remediation plan and production QA backlog.")
    return handoff_packet.model_copy(
        update={
            "produced_artifacts": _dedupe(list(handoff_packet.produced_artifacts) + refreshed_artifacts + [report_name]),
            "reviewed_artifacts": _dedupe(list(handoff_packet.reviewed_artifacts) + [report_name, DEFAULT_STATE_FILENAMES["qa_report"]]),
            "open_issues": _dedupe(
                [finding.summary for finding in qa_report.findings if finding.status.value == "open"]
                + [f"Approval packet {packet_id} is still pending." for packet_id in pending_packet_ids]
                + [f"Blocked upstream issue {issue_id} still needs manual review." for issue_id in blocked_issue_ids]
            ),
            "verification_items_open": _dedupe(
                [finding.recommendation for finding in qa_report.findings if finding.blocking and finding.status.value == "open"]
                + [f"Approval packet {packet_id}" for packet_id in pending_packet_ids]
            ),
            "pending_approval_packet_ids": list(pending_packet_ids),
            "pending_upstream_fix_ids": list(remaining_fix_ids),
            "handoff_instructions": _dedupe(instructions),
            "next_recommended_batch_id": remediation_plan.next_recommended_batch_id or handoff_packet.next_recommended_batch_id,
            "generated_at": datetime.now(UTC),
        }
    )


def _build_report_delta_result(
    delta: AuthoringDeltaRecord,
    *,
    packet_id: str | None,
    approval_status: ApprovalDecisionStatus,
    apply_status: ApplyDecisionStatus,
    model_by_artifact: dict[UpstreamArtifactName, object],
    selection_map: dict[str, str],
    notes: list[str] | None = None,
) -> ApprovedApplyDeltaResult:
    before_value = None
    after_value = None
    result_notes = list(notes or [])
    model = model_by_artifact.get(delta.target_artifact)
    if model is None:
        result_notes.append(f"Target artifact {delta.target_artifact.value} is unavailable in the current state package.")
    else:
        try:
            node = _resolve_selector_node(_clone_payload(model), delta.selector)
            raw_before = _read_field_value(node, delta.field_path)
            before_value = None if raw_before is MISSING else raw_before
            try:
                selected_option_id, selected_value = _selected_option(delta, selection_map)
            except (_SkipDelta, _BlockedDelta) as exc:
                result_notes.append(str(exc))
            else:
                after_value = selected_value
                if selected_option_id is not None:
                    selection_map.setdefault(delta.delta_id, selected_option_id)
        except Exception as exc:
            result_notes.append(str(exc))
    return ApprovedApplyDeltaResult(
        delta_id=delta.delta_id,
        fix_id=delta.fix_id,
        packet_id=packet_id,
        finding_ids=list(delta.source_finding_ids),
        target_artifact=delta.target_artifact,
        selector=delta.selector,
        field_path=delta.field_path,
        operation=delta.operation,
        approval_status=approval_status,
        apply_status=apply_status,
        before_value=before_value,
        after_value=after_value,
        selected_option_id=selection_map.get(delta.delta_id) or delta.selected_option_id,
        notes=result_notes,
    )


def _effective_fix_approval(
    fix: UpstreamFixProposal,
    *,
    packet: ApprovalPacket | None,
    approved_packet_ids: set[str],
    approved_fix_ids: set[str],
) -> tuple[ApprovalDecisionStatus, bool, list[str]]:
    notes: list[str] = []
    packet_explicit = packet is not None and (
        packet.approval_status == ApprovalDecisionStatus.APPROVED or packet.packet_id in approved_packet_ids
    )
    fix_explicit = fix.approval_status == ApprovalDecisionStatus.APPROVED or fix.fix_id in approved_fix_ids
    packet_rejected = packet is not None and (
        packet.approval_status == ApprovalDecisionStatus.REJECTED and packet.packet_id not in approved_packet_ids
    )
    fix_rejected = fix.approval_status == ApprovalDecisionStatus.REJECTED and fix.fix_id not in approved_fix_ids
    if packet_rejected or fix_rejected:
        return ApprovalDecisionStatus.REJECTED, False, notes
    if packet_explicit:
        return ApprovalDecisionStatus.APPROVED, True, notes
    if not fix_explicit:
        return ApprovalDecisionStatus.PENDING, False, notes
    if packet is not None:
        if packet.approval_mode == PacketApprovalMode.BUNDLE_REQUIRED:
            notes.append(
                f"Packet {packet.packet_id} requires bundle approval; fix-level approval for {fix.fix_id} is insufficient."
            )
            return ApprovalDecisionStatus.APPROVED, False, notes
        if len(packet.included_fix_ids) > 1:
            notes.append(
                f"Packet {packet.packet_id} groups multiple fixes; apply the packet approval explicitly to avoid partial bundle drift."
            )
            return ApprovalDecisionStatus.APPROVED, False, notes
    return ApprovalDecisionStatus.APPROVED, True, notes


def _range_to_numbers(slide_range: SlideRange) -> set[int]:
    return set(range(slide_range.start, slide_range.end + 1))


def _phase5_follow_on_reruns(
    *,
    fix_results: list[ApprovedApplyFixResult],
    asset_requests: AssetRequests | None,
    viz_spec: VizSpecSet | None,
) -> list[str]:
    follow_on: list[str] = []
    affected_slides: set[int] = set()
    for result in fix_results:
        if "derive-assets" in result.downstream_rerun_stages_selected:
            affected_slides.update(_range_to_numbers(result.affected_slide_range))
    if not affected_slides:
        return []
    if asset_requests is not None:
        requests = [request for request in asset_requests.requests if request.slide_number in affected_slides]
        if any(_request_needs_crop_rerun(request) for request in requests):
            follow_on.extend(["extract-assets", "review-crops"])
        if any(not _request_needs_crop_rerun(request) for request in requests):
            follow_on.append("render-visuals")
    if viz_spec is not None and any(spec.slide_number in affected_slides for spec in viz_spec.specs):
        follow_on.append("render-visuals")
    return _ordered_reruns(follow_on)


def _rebuild_upstream_fix_plan(
    upstream_fix_plan: UpstreamFixPlan,
    *,
    fixes: list[UpstreamFixProposal],
    approval_packets: list[ApprovalPacket],
    deltas: list[AuthoringDeltaRecord],
) -> UpstreamFixPlan:
    remaining_fixes = [
        fix
        for fix in fixes
        if fix.apply_status in {
            ApplyDecisionStatus.PENDING,
            ApplyDecisionStatus.DEFERRED,
            ApplyDecisionStatus.BLOCKED,
            ApplyDecisionStatus.FAILED,
        }
    ]
    packet_by_fix = {
        fix_id: packet.packet_id
        for packet in approval_packets
        for fix_id in packet.included_fix_ids
    }
    artifact_counts: dict[UpstreamArtifactName, dict[str, Any]] = {}
    rerun_counts: dict[str, int] = {}
    deltas_by_fix = {}
    for delta in deltas:
        deltas_by_fix.setdefault(delta.fix_id, []).append(delta)
    for fix in remaining_fixes:
        delta_buckets = deltas_by_fix.get(fix.fix_id, [])
        delta_counts_by_artifact: dict[UpstreamArtifactName, int] = {}
        for delta in delta_buckets:
            delta_counts_by_artifact[delta.target_artifact] = delta_counts_by_artifact.get(delta.target_artifact, 0) + 1
        for artifact in fix.target_artifacts:
            bucket = artifact_counts.setdefault(
                artifact,
                {"fix_count": 0, "delta_count": 0, "packet_ids": []},
            )
            bucket["fix_count"] += 1
            bucket["delta_count"] += delta_counts_by_artifact.get(artifact, 0)
            packet_id = packet_by_fix.get(fix.fix_id)
            if packet_id is not None:
                bucket["packet_ids"].append(packet_id)
        for stage in fix.downstream_rerun_stages:
            rerun_counts[stage] = rerun_counts.get(stage, 0) + 1
    impact_summary = [
        {
            "artifact": artifact.value,
            "fix_count": bucket["fix_count"],
            "delta_count": bucket["delta_count"],
            "packet_ids": _dedupe(bucket["packet_ids"]),
        }
        for artifact, bucket in artifact_counts.items()
    ]
    return upstream_fix_plan.model_copy(
        update={
            "actionable_upstream_issue_count": len(remaining_fixes),
            "fixes": fixes,
            "approval_packets": approval_packets,
            "artifact_impact_summary": impact_summary,
            "rerun_impact_summary": rerun_counts,
        }
    )


def _build_report_id(upstream_fix_plan: UpstreamFixPlan) -> str:
    suffix = upstream_fix_plan.plan_id.removeprefix("upstream-fix-plan-")
    return f"approved-apply-{suffix or upstream_fix_plan.plan_id}"


def apply_approved_fixes(
    *,
    approval_packet: ApprovalPacketSet,
    authoring_deltas: AuthoringDeltas,
    upstream_fix_plan: UpstreamFixPlan,
    remediation_plan: RemediationPlan,
    remediation_execution_report: RemediationExecutionReport,
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
    handoff_packet: HandoffPacket | None = None,
    workflow_plan: WorkflowPlan | None = None,
    asset_requests: AssetRequests | None = None,
    viz_spec: VizSpecSet | None = None,
    approved_packet_ids: list[str] | None = None,
    approved_fix_ids: list[str] | None = None,
    selected_delta_options: dict[str, str] | None = None,
    artifact_root: str | Path | None = None,
    state_output_dir: str | Path | None = None,
    build_output_dir: str | Path | None = None,
    asset_output_dir: str | Path | None = None,
    visual_output_dir: str | Path | None = None,
    notes_path: str | Path | None = None,
) -> ApprovedApplyOutputs:
    del notes_path
    artifact_root_path = Path(artifact_root).resolve() if artifact_root is not None else Path.cwd().resolve()
    state_root = Path(state_output_dir).resolve() if state_output_dir is not None else artifact_root_path
    build_root = Path(build_output_dir).resolve() if build_output_dir is not None else state_root
    asset_root = Path(asset_output_dir).resolve() if asset_output_dir is not None else state_root
    visual_root = Path(visual_output_dir).resolve() if visual_output_dir is not None else state_root
    pointer_root = _canonical_state_root(state_capsule, state_root, artifact_root_path)
    qa_governance_path = state_root / DEFAULT_STATE_FILENAMES["qa_governance"]
    qa_governance = load_state_file(qa_governance_path) if qa_governance_path.is_file() else None
    if qa_governance is not None and qa_governance.schema_name != "qa_governance":
        raise TypeError(f"expected qa_governance, found {qa_governance.schema_name}")

    approved_packet_set = set(approved_packet_ids or [])
    approved_fix_set = set(approved_fix_ids or [])
    selection_map = _selection_map(approval_packet, selected_delta_options)
    packet_by_fix = _fix_to_packet_map(approval_packet)
    delta_by_id = {delta.delta_id: delta for delta in authoring_deltas.deltas}
    report_warnings: list[str] = []

    current_models = _artifact_model_map(
        blueprint=blueprint,
        design_system=design_system,
        deck_constitution=deck_constitution,
        layout_library=layout_library,
        slide_ledger=slide_ledger,
        asset_requests=asset_requests,
        viz_spec=viz_spec,
    )

    fix_results: list[ApprovedApplyFixResult] = []
    planned_reruns_by_fix: dict[str, list[str]] = {}
    changed_artifacts: set[UpstreamArtifactName] = set()

    for fix in upstream_fix_plan.fixes:
        packet = packet_by_fix.get(fix.fix_id)
        approval_status, can_apply, approval_notes = _effective_fix_approval(
            fix,
            packet=packet,
            approved_packet_ids=approved_packet_set,
            approved_fix_ids=approved_fix_set,
        )
        missing_delta_ids = [delta_id for delta_id in fix.delta_ids if delta_id not in delta_by_id]
        if missing_delta_ids:
            raise KeyError(f"fix {fix.fix_id} references unknown delta ids: {missing_delta_ids}")
        deltas = [delta_by_id[delta_id] for delta_id in fix.delta_ids]

        if approval_status == ApprovalDecisionStatus.REJECTED:
            delta_results = [
                _build_report_delta_result(
                    delta,
                    packet_id=packet.packet_id if packet is not None else None,
                    approval_status=approval_status,
                    apply_status=ApplyDecisionStatus.SKIPPED,
                    model_by_artifact=current_models,
                    selection_map=selection_map,
                    notes=["The fix was explicitly rejected and was not applied."],
                )
                for delta in deltas
            ]
            fix_results.append(
                ApprovedApplyFixResult(
                    fix_id=fix.fix_id,
                    packet_id=packet.packet_id if packet is not None else None,
                    finding_ids=list(fix.source_finding_ids),
                    source_action_ids=list(fix.source_action_ids),
                    approval_status=approval_status,
                    apply_status=ApplyDecisionStatus.SKIPPED,
                    target_artifacts=list(fix.target_artifacts),
                    delta_ids=list(fix.delta_ids),
                    affected_slide_range=fix.affected_slide_range,
                    downstream_rerun_stages_requested=list(fix.downstream_rerun_stages),
                    downstream_rerun_stages_selected=[],
                    delta_results=delta_results,
                    notes=["The fix was explicitly rejected and remains unapplied."],
                )
            )
            continue

        if not can_apply:
            status = ApplyDecisionStatus.BLOCKED if approval_status == ApprovalDecisionStatus.APPROVED else ApplyDecisionStatus.DEFERRED
            notes = approval_notes or (
                ["The fix is still pending explicit approval and remains deferred."]
                if approval_status == ApprovalDecisionStatus.PENDING
                else ["The fix could not be applied safely from the current approval selection."]
            )
            delta_results = [
                _build_report_delta_result(
                    delta,
                    packet_id=packet.packet_id if packet is not None else None,
                    approval_status=approval_status,
                    apply_status=status,
                    model_by_artifact=current_models,
                    selection_map=selection_map,
                    notes=list(notes),
                )
                for delta in deltas
            ]
            fix_results.append(
                ApprovedApplyFixResult(
                    fix_id=fix.fix_id,
                    packet_id=packet.packet_id if packet is not None else None,
                    finding_ids=list(fix.source_finding_ids),
                    source_action_ids=list(fix.source_action_ids),
                    approval_status=approval_status,
                    apply_status=status,
                    target_artifacts=list(fix.target_artifacts),
                    delta_ids=list(fix.delta_ids),
                    affected_slide_range=fix.affected_slide_range,
                    downstream_rerun_stages_requested=list(fix.downstream_rerun_stages),
                    downstream_rerun_stages_selected=[],
                    delta_results=delta_results,
                    notes=list(notes),
                )
            )
            continue

        candidate_payloads: dict[UpstreamArtifactName, dict[str, Any]] = {}
        candidate_models = dict(current_models)
        delta_results: list[ApprovedApplyDeltaResult] = []
        changed_this_fix: set[UpstreamArtifactName] = set()
        fix_notes = list(approval_notes)
        apply_status = ApplyDecisionStatus.APPLIED

        try:
            for delta in deltas:
                model = candidate_models.get(delta.target_artifact)
                if model is None:
                    raise _BlockedDelta(f"Target artifact {delta.target_artifact.value} is unavailable for fix {fix.fix_id}.")
                payload = candidate_payloads.setdefault(delta.target_artifact, _clone_payload(model))
                node = _resolve_selector_node(payload, delta.selector)
                preview = _preview_delta(node, delta, selection_map)
                if preview.changed:
                    changed_this_fix.add(delta.target_artifact)
                delta_results.append(
                    ApprovedApplyDeltaResult(
                        delta_id=delta.delta_id,
                        fix_id=fix.fix_id,
                        packet_id=packet.packet_id if packet is not None else None,
                        finding_ids=list(delta.source_finding_ids),
                        target_artifact=delta.target_artifact,
                        selector=delta.selector,
                        field_path=delta.field_path,
                        operation=delta.operation,
                        approval_status=approval_status,
                        apply_status=ApplyDecisionStatus.APPLIED,
                        before_value=preview.before_value,
                        after_value=preview.after_value,
                        selected_option_id=preview.selected_option_id,
                        notes=list(preview.notes),
                    )
                )

            for artifact, payload in candidate_payloads.items():
                candidate_models[artifact] = current_models[artifact].__class__.model_validate(payload)
            current_models = candidate_models
            planned_reruns = _plan_fix_reruns(
                fix,
                deltas,
                asset_requests=current_models.get(UpstreamArtifactName.ASSET_REQUESTS),
            )
            planned_reruns_by_fix[fix.fix_id] = planned_reruns
            changed_artifacts.update(changed_this_fix)
            if not changed_this_fix:
                fix_notes.append("All targeted fields already matched the approved values; the fix was treated as idempotently applied.")
        except _BlockedDelta as exc:
            apply_status = ApplyDecisionStatus.BLOCKED
            fix_notes.append(str(exc))
            delta_results = [
                _build_report_delta_result(
                    delta,
                    packet_id=packet.packet_id if packet is not None else None,
                    approval_status=approval_status,
                    apply_status=ApplyDecisionStatus.BLOCKED,
                    model_by_artifact=current_models,
                    selection_map=selection_map,
                    notes=[str(exc), "No upstream artifact changes were committed for this fix."],
                )
                for delta in deltas
            ]
        except Exception as exc:
            apply_status = ApplyDecisionStatus.FAILED
            fix_notes.append(str(exc))
            delta_results = [
                _build_report_delta_result(
                    delta,
                    packet_id=packet.packet_id if packet is not None else None,
                    approval_status=approval_status,
                    apply_status=ApplyDecisionStatus.FAILED,
                    model_by_artifact=current_models,
                    selection_map=selection_map,
                    notes=[str(exc), "No upstream artifact changes were committed because transactional validation failed."],
                )
                for delta in deltas
            ]

        fix_results.append(
            ApprovedApplyFixResult(
                fix_id=fix.fix_id,
                packet_id=packet.packet_id if packet is not None else None,
                finding_ids=list(fix.source_finding_ids),
                source_action_ids=list(fix.source_action_ids),
                approval_status=approval_status,
                apply_status=apply_status,
                target_artifacts=list(fix.target_artifacts),
                delta_ids=list(fix.delta_ids),
                affected_slide_range=fix.affected_slide_range,
                downstream_rerun_stages_requested=list(fix.downstream_rerun_stages),
                downstream_rerun_stages_selected=list(planned_reruns_by_fix.get(fix.fix_id, [])),
                delta_results=delta_results,
                notes=fix_notes,
            )
        )

    blueprint = current_models[UpstreamArtifactName.BLUEPRINT]
    design_system = current_models[UpstreamArtifactName.DESIGN_SYSTEM]
    deck_constitution = current_models[UpstreamArtifactName.DECK_CONSTITUTION]
    layout_library = current_models[UpstreamArtifactName.LAYOUT_LIBRARY]
    slide_ledger = current_models[UpstreamArtifactName.SLIDE_LEDGER]
    asset_requests = current_models.get(UpstreamArtifactName.ASSET_REQUESTS)
    viz_spec = current_models.get(UpstreamArtifactName.VIZ_SPEC)

    rerun_stages = _ordered_reruns(
        [stage for stages in planned_reruns_by_fix.values() for stage in stages if stage]
    )
    if "derive-assets" in rerun_stages:
        derivation_outputs = derive_assets_from_blueprint(
            blueprint=blueprint,
            design_system=design_system,
            deck_constitution=deck_constitution,
            layout_library=layout_library,
            slide_ledger=slide_ledger,
            asset_requests=asset_requests,
        )
        asset_requests = derivation_outputs.asset_requests
        viz_spec = derivation_outputs.viz_spec
        slide_ledger = derivation_outputs.slide_ledger
        current_models = _artifact_model_map(
            blueprint=blueprint,
            design_system=design_system,
            deck_constitution=deck_constitution,
            layout_library=layout_library,
            slide_ledger=slide_ledger,
            asset_requests=asset_requests,
            viz_spec=viz_spec,
        )
        rerun_stages = _ordered_reruns(
            rerun_stages
            + _phase5_follow_on_reruns(
                fix_results=fix_results,
                asset_requests=asset_requests,
                viz_spec=viz_spec,
            )
        )

    if "extract-assets" in rerun_stages or "review-crops" in rerun_stages:
        if asset_requests is None:
            raise ValueError("extract-assets requires asset_requests after approved upstream deltas are applied")
        crop_outputs = run_document_asset_crop(
            asset_requests=asset_requests,
            slide_ledger=slide_ledger,
            output_dir=asset_root,
            asset_manifest=asset_manifest,
            root=artifact_root_path,
        )
        write_document_crop_outputs(crop_outputs, asset_root)
        asset_manifest = crop_outputs.asset_manifest
        slide_ledger = crop_outputs.slide_ledger
        if "review-crops" in rerun_stages:
            review_outputs = run_document_crop_review(
                asset_requests=asset_requests,
                crop_candidates=crop_outputs.crop_candidates,
                asset_manifest=asset_manifest,
                slide_ledger=slide_ledger,
                output_dir=asset_root,
                crop_review_inputs=crop_outputs.crop_review_inputs,
                crop_review_decisions=crop_outputs.crop_review_decisions,
                selected_crops=crop_outputs.selected_crops,
                root=artifact_root_path,
            )
            write_document_crop_outputs(review_outputs, asset_root)
            asset_manifest = review_outputs.asset_manifest
            slide_ledger = review_outputs.slide_ledger

    if "render-visuals" in rerun_stages:
        visual_outputs = run_structured_visuals(
            viz_spec=viz_spec,
            design_system=design_system,
            deck_constitution=deck_constitution,
            layout_library=layout_library,
            slide_ledger=slide_ledger,
            output_dir=visual_root,
            asset_requests=asset_requests,
            asset_manifest=asset_manifest,
            viz_manifest=viz_manifest,
            blueprint=blueprint,
            root=artifact_root_path,
        )
        write_structured_visual_outputs(visual_outputs, visual_root)
        viz_manifest = visual_outputs.viz_manifest
        asset_manifest = visual_outputs.asset_manifest
        slide_ledger = visual_outputs.slide_ledger

    pptx_path: Path | None = None
    if "compile-pptx" in rerun_stages:
        compile_outputs = compile_pptx(
            blueprint=blueprint,
            design_system=design_system,
            deck_constitution=deck_constitution,
            layout_library=layout_library,
            slide_ledger=slide_ledger,
            asset_manifest=asset_manifest,
            viz_manifest=viz_manifest,
            output_dir=build_root,
            batch_manifest=batch_manifest,
            state_capsule=state_capsule,
            root=artifact_root_path,
        )
        build_manifest = compile_outputs.build_manifest
        slide_build_linkage = compile_outputs.slide_build_linkage
        slide_ledger = compile_outputs.slide_ledger
        if compile_outputs.batch_manifest is not None:
            batch_manifest = compile_outputs.batch_manifest
        if compile_outputs.state_capsule is not None:
            state_capsule = compile_outputs.state_capsule
        pptx_path = compile_outputs.pptx_path

    if "qa-deck" in rerun_stages:
        qa_outputs = run_deck_qa(
            blueprint=blueprint,
            design_system=design_system,
            deck_constitution=deck_constitution,
            layout_library=layout_library,
            slide_ledger=slide_ledger,
            asset_manifest=asset_manifest,
            viz_manifest=viz_manifest,
            build_manifest=build_manifest,
            slide_build_linkage=slide_build_linkage,
            state_capsule=state_capsule,
            prior_report=qa_report,
            qa_governance=qa_governance,
            artifact_root=artifact_root_path,
        )
        qa_report = qa_outputs.qa_report
        qa_governance = qa_outputs.qa_governance or qa_governance
        slide_ledger = qa_outputs.slide_ledger
        slide_build_linkage = qa_outputs.slide_build_linkage
        if qa_outputs.state_capsule is not None:
            state_capsule = qa_outputs.state_capsule

    if "orchestrate-large-deck" in rerun_stages:
        if workflow_plan is None:
            raise ValueError("orchestrate-large-deck requires workflow_plan in canonical state or explicit input")
        orchestration_outputs = orchestrate_large_deck(
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
            canonical_state_root=pointer_root,
        )
        batch_manifest = orchestration_outputs.batch_manifest
        context_lock = orchestration_outputs.context_lock
        handoff_packet = orchestration_outputs.handoff_packet
        state_capsule = orchestration_outputs.state_capsule
        remediation_plan = orchestration_outputs.remediation_plan
        slide_ledger = orchestration_outputs.slide_ledger
        if orchestration_outputs.slide_build_linkage is not None:
            slide_build_linkage = orchestration_outputs.slide_build_linkage

    fix_status_by_id = {result.fix_id: result.apply_status for result in fix_results}
    approval_status_by_fix_id = {result.fix_id: result.approval_status for result in fix_results}
    updated_fixes = [
        fix.model_copy(
            update={
                "approval_status": approval_status_by_fix_id.get(fix.fix_id, fix.approval_status),
                "apply_status": fix_status_by_id.get(fix.fix_id, fix.apply_status),
            }
        )
        for fix in upstream_fix_plan.fixes
    ]

    delta_result_by_id = {
        delta_result.delta_id: delta_result
        for fix_result in fix_results
        for delta_result in fix_result.delta_results
    }
    updated_deltas = [
        delta.model_copy(
            update={
                "approval_status": delta_result_by_id[delta.delta_id].approval_status,
                "apply_status": delta_result_by_id[delta.delta_id].apply_status,
                "selected_option_id": delta_result_by_id[delta.delta_id].selected_option_id or delta.selected_option_id,
            }
        )
        if delta.delta_id in delta_result_by_id
        else delta
        for delta in authoring_deltas.deltas
    ]

    fix_result_by_id = {result.fix_id: result for result in fix_results}
    updated_packets: list[ApprovalPacket] = []
    for packet in approval_packet.packets:
        fully_approved = packet.approval_status == ApprovalDecisionStatus.APPROVED or packet.packet_id in approved_packet_set
        selected_options = {selection.delta_id: selection.option_id for selection in packet.selected_delta_options}
        for fix_id in packet.included_fix_ids:
            result = fix_result_by_id.get(fix_id)
            if result is None:
                continue
            for delta_result in result.delta_results:
                if delta_result.selected_option_id is not None:
                    selected_options[delta_result.delta_id] = delta_result.selected_option_id
        packet_approval_status, packet_apply_status = _packet_status_from_fixes(
            packet,
            fully_approved=fully_approved,
            fix_statuses=fix_status_by_id,
        )
        updated_packets.append(
            packet.model_copy(
                update={
                    "approval_status": packet_approval_status,
                    "apply_status": packet_apply_status,
                    "selected_delta_options": [
                        DeltaOptionSelection(delta_id=delta_id, option_id=option_id)
                        for delta_id, option_id in sorted(selected_options.items())
                    ],
                }
            )
        )

    approval_packet = approval_packet.model_copy(update={"packets": updated_packets})
    authoring_deltas = authoring_deltas.model_copy(update={"deltas": updated_deltas})
    upstream_fix_plan = _rebuild_upstream_fix_plan(
        upstream_fix_plan,
        fixes=updated_fixes,
        approval_packets=updated_packets,
        deltas=updated_deltas,
    )

    pending_packet_ids = [
        packet.packet_id
        for packet in updated_packets
        if packet.approval_status == ApprovalDecisionStatus.PENDING
        or packet.apply_status in {ApplyDecisionStatus.DEFERRED, ApplyDecisionStatus.BLOCKED, ApplyDecisionStatus.FAILED}
    ]
    remaining_fix_ids = [
        fix.fix_id
        for fix in updated_fixes
        if fix.apply_status in {
            ApplyDecisionStatus.PENDING,
            ApplyDecisionStatus.DEFERRED,
            ApplyDecisionStatus.BLOCKED,
            ApplyDecisionStatus.FAILED,
        }
    ]
    blocked_issue_ids = [item.issue_id for item in upstream_fix_plan.blocked_manual_items]

    canonical_artifacts = [
        _display_path(state_root / DEFAULT_STATE_FILENAMES["approved_apply_report"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["blueprint"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["design_system"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["deck_constitution"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["layout_library"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["slide_ledger"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["asset_manifest"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["viz_manifest"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["qa_report"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["batch_manifest"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["context_lock"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["state_capsule"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["remediation_plan"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["remediation_execution_report"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["upstream_fix_plan"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["approval_packet"], artifact_root_path),
        _display_path(state_root / DEFAULT_STATE_FILENAMES["authoring_deltas"], artifact_root_path),
        _display_path(build_root / "build-manifest.json", artifact_root_path),
        _display_path(build_root / "slide-build-linkage.json", artifact_root_path),
    ]
    if asset_requests is not None:
        canonical_artifacts.append(_display_path(state_root / DEFAULT_STATE_FILENAMES["asset_requests"], artifact_root_path))
    if viz_spec is not None:
        canonical_artifacts.append(_display_path(state_root / DEFAULT_STATE_FILENAMES["viz_spec"], artifact_root_path))
    if handoff_packet is not None:
        canonical_artifacts.append(_display_path(state_root / DEFAULT_STATE_FILENAMES["handoff_packet"], artifact_root_path))
    if pptx_path is not None:
        canonical_artifacts.append(_display_path(pptx_path, artifact_root_path))

    state_capsule = _update_state_capsule(
        state_capsule,
        qa_report=qa_report,
        remediation_plan=remediation_plan,
        pending_packet_ids=pending_packet_ids,
        remaining_fix_ids=remaining_fix_ids,
        blocked_issue_ids=blocked_issue_ids,
        pointer_root=pointer_root,
        warnings=report_warnings,
    )
    handoff_packet = _update_handoff_packet(
        handoff_packet,
        qa_report=qa_report,
        remediation_plan=remediation_plan,
        pending_packet_ids=pending_packet_ids,
        remaining_fix_ids=remaining_fix_ids,
        blocked_issue_ids=blocked_issue_ids,
        refreshed_artifacts=canonical_artifacts,
        report_name=DEFAULT_STATE_FILENAMES["approved_apply_report"],
    )

    summary = ApprovedApplySummary(
        total_proposals_seen=len(upstream_fix_plan.fixes),
        approved_proposals_seen=sum(1 for result in fix_results if result.approval_status == ApprovalDecisionStatus.APPROVED),
        applied_count=sum(1 for result in fix_results if result.apply_status == ApplyDecisionStatus.APPLIED),
        skipped_count=sum(1 for result in fix_results if result.apply_status == ApplyDecisionStatus.SKIPPED),
        deferred_count=sum(1 for result in fix_results if result.apply_status == ApplyDecisionStatus.DEFERRED),
        blocked_count=sum(1 for result in fix_results if result.apply_status == ApplyDecisionStatus.BLOCKED),
        failed_count=sum(1 for result in fix_results if result.apply_status == ApplyDecisionStatus.FAILED),
    )
    approved_apply_report = ApprovedApplyReport(
        report_id=_build_report_id(upstream_fix_plan),
        deck_title=upstream_fix_plan.deck_title,
        source_plan_id=upstream_fix_plan.plan_id,
        source_execution_report_id=upstream_fix_plan.source_execution_report_id,
        summary=summary,
        fix_results=fix_results,
        target_artifacts_touched=sorted(changed_artifacts, key=lambda artifact: artifact.value),
        downstream_stages_rerun=rerun_stages,
        canonical_artifacts_refreshed=_dedupe(canonical_artifacts),
        warnings=report_warnings,
        notes=[
            "Only explicitly approved bounded deltas were considered for apply.",
            "Downstream reruns stayed at worker-level scope because partial slide-level worker execution is not implemented.",
        ],
        remaining_pending_packet_ids=pending_packet_ids,
        remaining_pending_fix_ids=remaining_fix_ids,
        remaining_blocked_issue_ids=blocked_issue_ids,
        canonical_state_root=pointer_root,
    )

    return ApprovedApplyOutputs(
        approved_apply_report=approved_apply_report,
        blueprint=blueprint,
        design_system=design_system,
        deck_constitution=deck_constitution,
        layout_library=layout_library,
        slide_ledger=slide_ledger,
        asset_requests=asset_requests,
        viz_spec=viz_spec,
        asset_manifest=asset_manifest,
        viz_manifest=viz_manifest,
        build_manifest=build_manifest,
        qa_report=qa_report,
        qa_governance=qa_governance,
        slide_build_linkage=slide_build_linkage,
        batch_manifest=batch_manifest,
        context_lock=context_lock,
        handoff_packet=handoff_packet,
        state_capsule=state_capsule,
        remediation_plan=remediation_plan,
        remediation_execution_report=remediation_execution_report,
        upstream_fix_plan=upstream_fix_plan,
        approval_packet=approval_packet,
        authoring_deltas=authoring_deltas,
        pptx_path=pptx_path,
    )


def apply_approved_fixes_from_files(
    approval_packet_path: str | Path,
    authoring_deltas_path: str | Path,
    upstream_fix_plan_path: str | Path,
    remediation_plan_path: str | Path,
    remediation_execution_report_path: str | Path,
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
    handoff_packet_path: str | Path | None = None,
    workflow_plan_path: str | Path | None = None,
    asset_requests_path: str | Path | None = None,
    viz_spec_path: str | Path | None = None,
    approved_packet_ids: list[str] | None = None,
    approved_fix_ids: list[str] | None = None,
    selected_delta_options: dict[str, str] | None = None,
    artifact_root: str | Path | None = None,
    state_output_dir: str | Path | None = None,
    build_output_dir: str | Path | None = None,
    asset_output_dir: str | Path | None = None,
    visual_output_dir: str | Path | None = None,
    notes_path: str | Path | None = None,
) -> ApprovedApplyOutputs:
    approval_packet = load_state_file(approval_packet_path)
    authoring_deltas = load_state_file(authoring_deltas_path)
    upstream_fix_plan = load_state_file(upstream_fix_plan_path)
    remediation_plan = load_state_file(remediation_plan_path)
    remediation_execution_report = load_state_file(remediation_execution_report_path)
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

    if approval_packet.schema_name != "approval_packet":
        raise TypeError(f"expected approval_packet, found {approval_packet.schema_name}")
    if authoring_deltas.schema_name != "authoring_deltas":
        raise TypeError(f"expected authoring_deltas, found {authoring_deltas.schema_name}")
    if upstream_fix_plan.schema_name != "upstream_fix_plan":
        raise TypeError(f"expected upstream_fix_plan, found {upstream_fix_plan.schema_name}")
    if remediation_plan.schema_name != "remediation_plan":
        raise TypeError(f"expected remediation_plan, found {remediation_plan.schema_name}")
    if remediation_execution_report.schema_name != "remediation_execution_report":
        raise TypeError(f"expected remediation_execution_report, found {remediation_execution_report.schema_name}")
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
    handoff_packet = _resolve_optional_input(
        handoff_packet_path,
        schema_name="handoff_packet",
        state_capsule=state_capsule,
        search_root=search_root,
        artifact_root=artifact_root_path,
    )
    workflow_plan = _resolve_optional_input(
        workflow_plan_path,
        schema_name="workflow_plan",
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

    return apply_approved_fixes(
        approval_packet=approval_packet,
        authoring_deltas=authoring_deltas,
        upstream_fix_plan=upstream_fix_plan,
        remediation_plan=remediation_plan,
        remediation_execution_report=remediation_execution_report,
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
        handoff_packet=handoff_packet,
        workflow_plan=workflow_plan,
        asset_requests=asset_requests,
        viz_spec=viz_spec,
        approved_packet_ids=approved_packet_ids,
        approved_fix_ids=approved_fix_ids,
        selected_delta_options=selected_delta_options,
        artifact_root=artifact_root_path,
        state_output_dir=state_output_dir,
        build_output_dir=build_output_dir,
        asset_output_dir=asset_output_dir,
        visual_output_dir=visual_output_dir,
        notes_path=notes_path,
    )


def write_approved_apply_outputs(
    outputs: ApprovedApplyOutputs,
    state_output_dir: str | Path,
    *,
    build_output_dir: str | Path | None = None,
) -> dict[str, Path]:
    state_root = Path(state_output_dir)
    state_root.mkdir(parents=True, exist_ok=True)
    build_root = Path(build_output_dir) if build_output_dir is not None else state_root
    build_root.mkdir(parents=True, exist_ok=True)
    written = {
        "approved_apply_report": save_state_file(
            outputs.approved_apply_report,
            state_root / DEFAULT_STATE_FILENAMES["approved_apply_report"],
        ),
        "blueprint": save_state_file(outputs.blueprint, state_root / DEFAULT_STATE_FILENAMES["blueprint"]),
        "design_system": save_state_file(outputs.design_system, state_root / DEFAULT_STATE_FILENAMES["design_system"]),
        "deck_constitution": save_state_file(
            outputs.deck_constitution,
            state_root / DEFAULT_STATE_FILENAMES["deck_constitution"],
        ),
        "layout_library": save_state_file(outputs.layout_library, state_root / DEFAULT_STATE_FILENAMES["layout_library"]),
        "slide_ledger": save_state_file(outputs.slide_ledger, state_root / DEFAULT_STATE_FILENAMES["slide_ledger"]),
        "asset_manifest": save_state_file(outputs.asset_manifest, state_root / DEFAULT_STATE_FILENAMES["asset_manifest"]),
        "viz_manifest": save_state_file(outputs.viz_manifest, state_root / DEFAULT_STATE_FILENAMES["viz_manifest"]),
        "qa_report": save_state_file(outputs.qa_report, state_root / DEFAULT_STATE_FILENAMES["qa_report"]),
        "batch_manifest": save_state_file(outputs.batch_manifest, state_root / DEFAULT_STATE_FILENAMES["batch_manifest"]),
        "context_lock": save_state_file(outputs.context_lock, state_root / DEFAULT_STATE_FILENAMES["context_lock"]),
        "state_capsule": save_state_file(outputs.state_capsule, state_root / DEFAULT_STATE_FILENAMES["state_capsule"]),
        "remediation_plan": save_state_file(outputs.remediation_plan, state_root / DEFAULT_STATE_FILENAMES["remediation_plan"]),
        "remediation_execution_report": save_state_file(
            outputs.remediation_execution_report,
            state_root / DEFAULT_STATE_FILENAMES["remediation_execution_report"],
        ),
        "upstream_fix_plan": save_state_file(outputs.upstream_fix_plan, state_root / DEFAULT_STATE_FILENAMES["upstream_fix_plan"]),
        "approval_packet": save_state_file(outputs.approval_packet, state_root / DEFAULT_STATE_FILENAMES["approval_packet"]),
        "authoring_deltas": save_state_file(outputs.authoring_deltas, state_root / DEFAULT_STATE_FILENAMES["authoring_deltas"]),
        "build_manifest": save_state_file(outputs.build_manifest, build_root / "build-manifest.json"),
        "slide_build_linkage": save_state_file(outputs.slide_build_linkage, build_root / "slide-build-linkage.json"),
    }
    if outputs.qa_governance is not None:
        written["qa_governance"] = save_state_file(
            outputs.qa_governance,
            state_root / DEFAULT_STATE_FILENAMES["qa_governance"],
        )
    if outputs.asset_requests is not None:
        written["asset_requests"] = save_state_file(outputs.asset_requests, state_root / DEFAULT_STATE_FILENAMES["asset_requests"])
    if outputs.viz_spec is not None:
        written["viz_spec"] = save_state_file(outputs.viz_spec, state_root / DEFAULT_STATE_FILENAMES["viz_spec"])
    if outputs.handoff_packet is not None:
        written["handoff_packet"] = save_state_file(outputs.handoff_packet, state_root / DEFAULT_STATE_FILENAMES["handoff_packet"])
    if outputs.pptx_path is not None:
        written["pptx"] = outputs.pptx_path
    return written


