"""Build history and release-note artifacts from migration readiness reports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .scene_migration_readiness import (
    MigrationReadinessBlocker,
    SceneMigrationReadinessReport,
)


SCENE_MIGRATION_HISTORY_REPORT_VERSION = "0.1"

MovementStatus = Literal["improved", "regressed", "unchanged", "mixed", "insufficient_history"]
BlockerChangeStatus = Literal["added", "resolved", "persisting"]
MetricDirection = Literal["improved", "regressed", "unchanged", "informational", "unavailable"]

RECOMMENDATION_ORDER = {
    "no_go": 1,
    "not_yet": 2,
    "ready_for_limited_default_path_poc": 3,
    "ready_for_default_path_migration_discussion": 4,
    "ready_for_visual_pinned_review": 5,
}

LOWER_IS_BETTER_METRICS = {
    "findings_count",
    "enforceable_count",
    "text_overflow_risk",
    "trace_missing",
    "duplicate_traces",
    "unresolved_style_token_count",
    "fallback_style_count",
    "style_findings",
    "adapter_findings",
    "placeholder_shape_count",
    "unsupported_layout_family_count",
    "visual_threshold_failures",
    "visual_missing_baselines",
    "blockers_count",
}
HIGHER_IS_BETTER_METRICS = {"nonvisual_ready_count"}
INFORMATIONAL_METRICS = {"fixture_count", "visual_smoke_ready_count", "visual_diff_ready_count"}


class SceneMigrationHistoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SceneMigrationHistoryEntry(SceneMigrationHistoryModel):
    label: str
    report_path: str
    overall_status: str
    recommendation: str
    blockers_count: int
    nonvisual_ready_count: int
    visual_smoke_ready_count: int
    visual_diff_ready_count: int
    structural_hash: str


class SceneMigrationMetricChange(SceneMigrationHistoryModel):
    metric: str
    previous: int | str | None = None
    current: int | str | None = None
    delta: int | None = None
    direction: MetricDirection = "unavailable"


class SceneMigrationBlockerChange(SceneMigrationHistoryModel):
    fixture_id: str
    profile: str
    category: str
    code: str
    status: BlockerChangeStatus
    previous_severity: str | None = None
    current_severity: str | None = None
    message: str
    suggested_next_action: str | None = None


class SceneMigrationReadinessMovement(SceneMigrationHistoryModel):
    status: MovementStatus
    recommendation_previous: str | None = None
    recommendation_current: str
    recommendation_changed: bool
    summary: str


class SceneMigrationReleaseNote(SceneMigrationHistoryModel):
    title: str = "Scene Migration Readiness Update"
    movement_summary: MovementStatus
    recommendation_current: str
    recommendation_previous: str | None = None
    blockers_added_count: int
    blockers_resolved_count: int
    blockers_persisting_count: int
    suggested_next_action: str


class SceneMigrationHistoryReport(SceneMigrationHistoryModel):
    report_version: str = SCENE_MIGRATION_HISTORY_REPORT_VERSION
    current_report_path: str
    previous_report_path: str | None = None
    history_input_paths: list[str]
    current_overall_status: str
    previous_overall_status: str | None = None
    recommendation_current: str
    recommendation_previous: str | None = None
    recommendation_changed: bool
    movement_summary: SceneMigrationReadinessMovement
    fixture_count_current: int
    fixture_count_previous: int | None = None
    new_fixtures: list[str] = Field(default_factory=list)
    removed_fixtures: list[str] = Field(default_factory=list)
    changed_fixtures: list[str] = Field(default_factory=list)
    blockers_added: list[SceneMigrationBlockerChange] = Field(default_factory=list)
    blockers_resolved: list[SceneMigrationBlockerChange] = Field(default_factory=list)
    blockers_persisting: list[SceneMigrationBlockerChange] = Field(default_factory=list)
    metric_deltas: list[SceneMigrationMetricChange] = Field(default_factory=list)
    visual_evidence_changes: list[SceneMigrationMetricChange] = Field(default_factory=list)
    generated_release_note_path: str | None = None
    entries: list[SceneMigrationHistoryEntry] = Field(default_factory=list)
    release_note: SceneMigrationReleaseNote
    structural_hash: str = ""

    def to_stable_payload(self, *, include_paths: bool = True) -> dict[str, Any]:
        return scene_migration_history_report_to_stable_payload(self, include_paths=include_paths)

    def to_stable_json(self) -> str:
        return scene_migration_history_report_to_stable_json(self)


def build_scene_migration_history(
    *,
    current_report_path: str | Path,
    previous_report_path: str | Path | None = None,
) -> SceneMigrationHistoryReport:
    current_path = Path(current_report_path).resolve()
    if not current_path.is_file():
        raise FileNotFoundError(f"current migration readiness report not found: {current_path}")
    current = _load_readiness_report(current_path)

    previous: SceneMigrationReadinessReport | None = None
    previous_path: Path | None = None
    if previous_report_path is not None:
        previous_path = Path(previous_report_path).resolve()
        if not previous_path.is_file():
            raise FileNotFoundError(f"previous migration readiness report not found: {previous_path}")
        previous = _load_readiness_report(previous_path)

    movement, metric_deltas, visual_changes = compare_scene_migration_reports(current, previous)
    blocker_changes = _blocker_changes(current, previous)
    previous_fixture_ids = set(previous.fixture_ids if previous is not None else [])
    current_fixture_ids = set(current.fixture_ids)
    changed_fixtures = _changed_fixtures(current, previous)

    release_note = SceneMigrationReleaseNote(
        movement_summary=movement.status,
        recommendation_current=current.default_migration_recommendation,
        recommendation_previous=previous.default_migration_recommendation if previous is not None else None,
        blockers_added_count=len(blocker_changes["added"]),
        blockers_resolved_count=len(blocker_changes["resolved"]),
        blockers_persisting_count=len(blocker_changes["persisting"]),
        suggested_next_action=_suggested_next_action(current, movement.status, blocker_changes["added"]),
    )
    report = SceneMigrationHistoryReport(
        current_report_path=str(current_path),
        previous_report_path=str(previous_path) if previous_path is not None else None,
        history_input_paths=[str(path) for path in ([previous_path] if previous_path is not None else []) + [current_path]],
        current_overall_status=current.overall_status,
        previous_overall_status=previous.overall_status if previous is not None else None,
        recommendation_current=current.default_migration_recommendation,
        recommendation_previous=previous.default_migration_recommendation if previous is not None else None,
        recommendation_changed=(
            previous is not None
            and previous.default_migration_recommendation != current.default_migration_recommendation
        ),
        movement_summary=movement,
        fixture_count_current=current.fixture_count,
        fixture_count_previous=previous.fixture_count if previous is not None else None,
        new_fixtures=sorted(current_fixture_ids - previous_fixture_ids) if previous is not None else [],
        removed_fixtures=sorted(previous_fixture_ids - current_fixture_ids) if previous is not None else [],
        changed_fixtures=changed_fixtures,
        blockers_added=blocker_changes["added"],
        blockers_resolved=blocker_changes["resolved"],
        blockers_persisting=blocker_changes["persisting"],
        metric_deltas=metric_deltas,
        visual_evidence_changes=visual_changes,
        entries=_history_entries(current_path, current, previous_path, previous),
        release_note=release_note,
        structural_hash="",
    )
    return report.model_copy(update={"structural_hash": scene_migration_history_report_structural_hash(report)})


def compare_scene_migration_reports(
    current: SceneMigrationReadinessReport,
    previous: SceneMigrationReadinessReport | None,
) -> tuple[SceneMigrationReadinessMovement, list[SceneMigrationMetricChange], list[SceneMigrationMetricChange]]:
    if previous is None:
        movement = SceneMigrationReadinessMovement(
            status="insufficient_history",
            recommendation_current=current.default_migration_recommendation,
            recommendation_changed=False,
            summary="No previous migration-readiness report was provided.",
        )
        return movement, [], []

    metric_deltas = _metric_deltas(current, previous)
    visual_changes = [delta for delta in metric_deltas if delta.metric in {"visual_smoke_ready_count", "visual_diff_ready_count"}]
    blocker_changes = _blocker_changes(current, previous)
    movement = _classify_movement(
        current=current,
        previous=previous,
        metric_deltas=metric_deltas,
        blockers_added=len(blocker_changes["added"]),
        blockers_resolved=len(blocker_changes["resolved"]),
    )
    return movement, metric_deltas, visual_changes


def build_scene_migration_release_notes(report: SceneMigrationHistoryReport) -> str:
    lines = [
        "# Scene Migration Readiness Release Note",
        "",
        "## Executive Summary",
        "",
        f"- Movement: `{report.movement_summary.status}`",
        f"- Current status: `{report.current_overall_status}`",
        f"- Current recommendation: `{report.recommendation_current}`",
    ]
    if report.recommendation_previous is None:
        lines.append("- Previous recommendation: unavailable")
    else:
        lines.append(f"- Previous recommendation: `{report.recommendation_previous}`")
    lines.extend(
        [
            f"- Recommendation changed: `{str(report.recommendation_changed).lower()}`",
            "",
            "## Overall Readiness",
            "",
            report.movement_summary.summary,
            "",
            "## Fixture Changes",
            "",
            f"- Current fixtures: {report.fixture_count_current}",
            f"- Previous fixtures: {report.fixture_count_previous if report.fixture_count_previous is not None else 'unavailable'}",
            f"- New fixtures: {_format_list(report.new_fixtures)}",
            f"- Removed fixtures: {_format_list(report.removed_fixtures)}",
            f"- Changed fixtures: {_format_list(report.changed_fixtures)}",
            "",
            "## Blockers Added",
            "",
        ]
    )
    lines.extend(_blocker_lines(report.blockers_added, "No new blockers were introduced."))
    lines.extend(["", "## Blockers Resolved", ""])
    lines.extend(_blocker_lines(report.blockers_resolved, "No blockers were resolved."))
    lines.extend(["", "## Persisting Blockers", ""])
    lines.extend(_blocker_lines(report.blockers_persisting, "No blockers are persisting."))
    lines.extend(["", "## Key Metric Changes", ""])
    if report.metric_deltas:
        for delta in report.metric_deltas:
            lines.append(
                f"- `{delta.metric}`: {delta.previous} -> {delta.current} "
                f"(delta={delta.delta}, `{delta.direction}`)"
            )
    else:
        lines.append("Metric deltas are unavailable because no previous report was provided.")
    lines.extend(["", "## Visual Evidence Changes", ""])
    if report.visual_evidence_changes:
        for delta in report.visual_evidence_changes:
            lines.append(f"- `{delta.metric}`: {delta.previous} -> {delta.current} (`{delta.direction}`)")
    else:
        lines.append("No visual evidence changes were detected.")
    lines.extend(
        [
            "",
            "## Artifact Paths",
            "",
            f"- Current report: `{report.current_report_path}`",
        ]
    )
    if report.previous_report_path is not None:
        lines.append(f"- Previous report: `{report.previous_report_path}`")
    lines.extend(["", "## Suggested Next Action", "", report.release_note.suggested_next_action])
    return "\n".join(lines) + "\n"


def write_scene_migration_history_artifacts(
    report: SceneMigrationHistoryReport,
    *,
    output_path: str | Path,
    markdown_path: str | Path | None = None,
) -> tuple[SceneMigrationHistoryReport, Path, Path | None]:
    json_path = Path(output_path)
    md_path: Path | None = Path(markdown_path) if markdown_path is not None else None
    report_to_write = report
    if md_path is not None:
        report_to_write = report.model_copy(update={"generated_release_note_path": str(md_path.resolve())})
        report_to_write = report_to_write.model_copy(
            update={"structural_hash": scene_migration_history_report_structural_hash(report_to_write)}
        )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(scene_migration_history_report_to_stable_json(report_to_write) + "\n", encoding="utf-8")
    if md_path is not None:
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(build_scene_migration_release_notes(report_to_write), encoding="utf-8")
    return report_to_write, json_path, md_path


def scene_migration_history_report_to_stable_payload(
    report: SceneMigrationHistoryReport,
    *,
    include_paths: bool = True,
) -> dict[str, Any]:
    payload = report.model_dump(mode="json", exclude_none=True, by_alias=True)
    if not include_paths:
        for key in (
            "current_report_path",
            "previous_report_path",
            "history_input_paths",
            "generated_release_note_path",
        ):
            payload.pop(key, None)
        for entry in payload.get("entries", []):
            entry.pop("report_path", None)
    return _normalize_for_stable_json(payload)


def scene_migration_history_report_to_stable_json(report: SceneMigrationHistoryReport) -> str:
    return json.dumps(
        scene_migration_history_report_to_stable_payload(report),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def scene_migration_history_report_structural_hash(report: SceneMigrationHistoryReport) -> str:
    payload = scene_migration_history_report_to_stable_payload(report, include_paths=False)
    payload.pop("structural_hash", None)
    stable_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


def summarize_scene_migration_history_report(report: SceneMigrationHistoryReport) -> list[str]:
    return [
        (
            "SCENE_MIGRATION_HISTORY "
            f"movement={report.movement_summary.status} "
            f"current_status={report.current_overall_status} "
            f"recommendation={report.recommendation_current} "
            f"recommendation_changed={str(report.recommendation_changed).lower()} "
            f"blockers_added={len(report.blockers_added)} "
            f"blockers_resolved={len(report.blockers_resolved)} "
            f"blockers_persisting={len(report.blockers_persisting)} "
            f"changed_fixtures={len(report.changed_fixtures)}"
        )
    ]


def _load_readiness_report(path: Path) -> SceneMigrationReadinessReport:
    return SceneMigrationReadinessReport.model_validate_json(path.read_text(encoding="utf-8"))


def _history_entries(
    current_path: Path,
    current: SceneMigrationReadinessReport,
    previous_path: Path | None,
    previous: SceneMigrationReadinessReport | None,
) -> list[SceneMigrationHistoryEntry]:
    entries: list[SceneMigrationHistoryEntry] = []
    if previous is not None and previous_path is not None:
        entries.append(_history_entry("previous", previous_path, previous))
    entries.append(_history_entry("current", current_path, current))
    return entries


def _history_entry(label: str, path: Path, report: SceneMigrationReadinessReport) -> SceneMigrationHistoryEntry:
    return SceneMigrationHistoryEntry(
        label=label,
        report_path=str(path),
        overall_status=report.overall_status,
        recommendation=report.default_migration_recommendation,
        blockers_count=len(report.blockers),
        nonvisual_ready_count=report.nonvisual_ready_count,
        visual_smoke_ready_count=report.visual_smoke_ready_count,
        visual_diff_ready_count=report.visual_diff_ready_count,
        structural_hash=report.structural_hash,
    )


def _classify_movement(
    *,
    current: SceneMigrationReadinessReport,
    previous: SceneMigrationReadinessReport,
    metric_deltas: list[SceneMigrationMetricChange],
    blockers_added: int,
    blockers_resolved: int,
) -> SceneMigrationReadinessMovement:
    current_rank = RECOMMENDATION_ORDER.get(current.default_migration_recommendation, 0)
    previous_rank = RECOMMENDATION_ORDER.get(previous.default_migration_recommendation, 0)
    recommendation_changed = current.default_migration_recommendation != previous.default_migration_recommendation
    if current_rank < previous_rank or blockers_added > 0:
        status: MovementStatus = "regressed"
    elif current_rank > previous_rank or blockers_resolved > 0:
        status = "improved"
    else:
        meaningful = [delta.direction for delta in metric_deltas if delta.direction in {"improved", "regressed"}]
        if "improved" in meaningful and "regressed" in meaningful:
            status = "mixed"
        elif "regressed" in meaningful:
            status = "regressed"
        elif "improved" in meaningful:
            status = "improved"
        else:
            status = "unchanged"
    return SceneMigrationReadinessMovement(
        status=status,
        recommendation_previous=previous.default_migration_recommendation,
        recommendation_current=current.default_migration_recommendation,
        recommendation_changed=recommendation_changed,
        summary=_movement_summary(status, current, previous, blockers_added, blockers_resolved),
    )


def _movement_summary(
    status: MovementStatus,
    current: SceneMigrationReadinessReport,
    previous: SceneMigrationReadinessReport,
    blockers_added: int,
    blockers_resolved: int,
) -> str:
    if status == "improved":
        return (
            "Readiness improved: "
            f"recommendation `{previous.default_migration_recommendation}` -> "
            f"`{current.default_migration_recommendation}`, blockers added={blockers_added}, "
            f"blockers resolved={blockers_resolved}."
        )
    if status == "regressed":
        return (
            "Readiness regressed: "
            f"recommendation `{previous.default_migration_recommendation}` -> "
            f"`{current.default_migration_recommendation}`, blockers added={blockers_added}, "
            f"blockers resolved={blockers_resolved}."
        )
    if status == "mixed":
        return "Readiness movement is mixed: some metrics improved while others regressed."
    return (
        "Readiness is unchanged: "
        f"current report remains `{current.overall_status}` with {len(current.blockers)} blocker(s)."
    )


def _blocker_changes(
    current: SceneMigrationReadinessReport,
    previous: SceneMigrationReadinessReport | None,
) -> dict[str, list[SceneMigrationBlockerChange]]:
    if previous is None:
        return {"added": [], "resolved": [], "persisting": []}
    previous_by_key = {_blocker_key(blocker): blocker for blocker in previous.blockers}
    current_by_key = {_blocker_key(blocker): blocker for blocker in current.blockers}
    added = [
        _blocker_change(current_by_key[key], "added", previous_blocker=None)
        for key in sorted(current_by_key.keys() - previous_by_key.keys())
    ]
    resolved = [
        _blocker_change(previous_by_key[key], "resolved", current_blocker=None)
        for key in sorted(previous_by_key.keys() - current_by_key.keys())
    ]
    persisting = [
        _blocker_change(current_by_key[key], "persisting", previous_blocker=previous_by_key[key])
        for key in sorted(current_by_key.keys() & previous_by_key.keys())
    ]
    return {"added": added, "resolved": resolved, "persisting": persisting}


def _blocker_key(blocker: MigrationReadinessBlocker) -> tuple[str, str, str, str, str]:
    return (blocker.fixture_id, blocker.profile, blocker.category, blocker.code, blocker.message)


def _blocker_change(
    blocker: MigrationReadinessBlocker,
    status: BlockerChangeStatus,
    *,
    previous_blocker: MigrationReadinessBlocker | None = None,
    current_blocker: MigrationReadinessBlocker | None = None,
) -> SceneMigrationBlockerChange:
    return SceneMigrationBlockerChange(
        fixture_id=blocker.fixture_id,
        profile=blocker.profile,
        category=blocker.category,
        code=blocker.code,
        status=status,
        previous_severity=(previous_blocker or blocker).severity if status != "added" else None,
        current_severity=(current_blocker or blocker).severity if status != "resolved" else None,
        message=blocker.message,
        suggested_next_action=blocker.suggested_next_action,
    )


def _metric_deltas(
    current: SceneMigrationReadinessReport,
    previous: SceneMigrationReadinessReport,
) -> list[SceneMigrationMetricChange]:
    current_metrics = _aggregate_metrics(current)
    previous_metrics = _aggregate_metrics(previous)
    deltas: list[SceneMigrationMetricChange] = []
    for metric in sorted(current_metrics):
        current_value = current_metrics[metric]
        previous_value = previous_metrics.get(metric)
        if previous_value is None:
            deltas.append(SceneMigrationMetricChange(metric=metric, current=current_value, direction="unavailable"))
            continue
        delta = int(current_value) - int(previous_value)
        deltas.append(
            SceneMigrationMetricChange(
                metric=metric,
                previous=int(previous_value),
                current=int(current_value),
                delta=delta,
                direction=_metric_direction(metric, delta),
            )
        )
    return deltas


def _aggregate_metrics(report: SceneMigrationReadinessReport) -> dict[str, int]:
    style_findings = sum(1 for blocker in report.blockers if blocker.category == "style_policy")
    return {
        "fixture_count": report.fixture_count,
        "nonvisual_ready_count": report.nonvisual_ready_count,
        "visual_smoke_ready_count": report.visual_smoke_ready_count,
        "visual_diff_ready_count": report.visual_diff_ready_count,
        "findings_count": sum(fixture.findings_count for fixture in report.per_fixture),
        "enforceable_count": sum(fixture.enforceable_count for fixture in report.per_fixture),
        "text_overflow_risk": sum(fixture.text_overflow_risk for fixture in report.per_fixture),
        "trace_missing": sum(fixture.trace_missing for fixture in report.per_fixture),
        "duplicate_traces": sum(fixture.duplicate_traces for fixture in report.per_fixture),
        "unresolved_style_token_count": sum(fixture.unresolved_style_token_count for fixture in report.per_fixture),
        "fallback_style_count": sum(fixture.fallback_style_count for fixture in report.per_fixture),
        "style_findings": style_findings,
        "adapter_findings": sum(fixture.adapter_findings for fixture in report.per_fixture),
        "placeholder_shape_count": sum(fixture.placeholder_shape_count for fixture in report.per_fixture),
        "unsupported_layout_family_count": sum(fixture.unsupported_layout_family_count for fixture in report.per_fixture),
        "visual_threshold_failures": sum(fixture.visual_threshold_failures for fixture in report.per_fixture),
        "visual_missing_baselines": sum(fixture.visual_missing_baselines for fixture in report.per_fixture),
        "blockers_count": len(report.blockers),
    }


def _metric_direction(metric: str, delta: int) -> MetricDirection:
    if delta == 0:
        return "unchanged"
    if metric in LOWER_IS_BETTER_METRICS:
        return "improved" if delta < 0 else "regressed"
    if metric in HIGHER_IS_BETTER_METRICS:
        return "improved" if delta > 0 else "regressed"
    if metric in INFORMATIONAL_METRICS:
        return "informational"
    return "informational"


def _changed_fixtures(
    current: SceneMigrationReadinessReport,
    previous: SceneMigrationReadinessReport | None,
) -> list[str]:
    if previous is None:
        return []
    previous_by_fixture = {fixture.fixture_id: fixture for fixture in previous.per_fixture}
    changed: list[str] = []
    for fixture in current.per_fixture:
        previous_fixture = previous_by_fixture.get(fixture.fixture_id)
        if previous_fixture is None or previous_fixture.overall_status != fixture.overall_status:
            changed.append(fixture.fixture_id)
    return sorted(changed)


def _suggested_next_action(
    current: SceneMigrationReadinessReport,
    movement: MovementStatus,
    blockers_added: list[SceneMigrationBlockerChange],
) -> str:
    if blockers_added:
        category = blockers_added[0].category
        return f"Investigate the new `{category}` blocker before using this readiness update as migration evidence."
    if current.default_migration_recommendation == "ready_for_limited_default_path_poc":
        return "Use this as non-visual evidence for a limited default-path POC; visual evidence remains optional and separate."
    if current.default_migration_recommendation == "ready_for_default_path_migration_discussion":
        return "Review visual-smoke artifacts alongside non-visual readiness before any default-path migration discussion."
    if current.default_migration_recommendation == "ready_for_visual_pinned_review":
        return "Review pinned visual evidence and baseline provenance before expanding default-path migration scope."
    if movement == "insufficient_history":
        return "Keep this as the first history artifact and compare the next dashboard report against it."
    return "Address the reported blockers before considering default-path migration work."


def _blocker_lines(changes: list[SceneMigrationBlockerChange], empty_message: str) -> list[str]:
    if not changes:
        return [empty_message]
    return [
        f"- `{change.fixture_id}` `{change.profile}` `{change.category}` `{change.code}`: {change.message}"
        for change in changes
    ]


def _format_list(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"


def _normalize_for_stable_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_for_stable_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize_for_stable_json(item) for item in value]
    if isinstance(value, float):
        normalized = round(value, 6)
        if normalized == 0:
            return 0
        if float(normalized).is_integer():
            return int(normalized)
        return normalized
    return value
