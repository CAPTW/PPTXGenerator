"""Aggregate existing scene readiness artifacts into migration-readiness evidence."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


SCENE_MIGRATION_READINESS_REPORT_VERSION = "0.1"
REQUIRED_MIGRATION_PROFILES = ("structural", "curated-strict")
OPTIONAL_MIGRATION_PROFILES = ("visual-smoke", "visual-diff-local", "visual-diff-pinned")
MIGRATION_PROFILES = (*REQUIRED_MIGRATION_PROFILES, *OPTIONAL_MIGRATION_PROFILES)

MigrationOverallStatus = Literal[
    "ready_nonvisual",
    "ready_nonvisual_visual_smoke_available",
    "ready_with_pinned_visual_evidence",
    "blocked_structural",
    "blocked_style",
    "blocked_adapter",
    "blocked_visual",
    "insufficient_evidence",
]
MigrationRecommendation = Literal[
    "no_go",
    "not_yet",
    "ready_for_limited_default_path_poc",
    "ready_for_default_path_migration_discussion",
    "ready_for_visual_pinned_review",
]
DeltaStatus = Literal["improved", "regressed", "unchanged", "unavailable"]


class SceneMigrationReadinessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProfileReadinessSummary(SceneMigrationReadinessModel):
    profile: str
    available: bool
    report_path: str | None = None
    status: str = "missing"
    readiness_profile: str | None = None
    object_status: str = "disabled"
    style_status: str = "disabled"
    adapter_status: str = "disabled"
    screenshot_status: str = "disabled"
    visual_status: str = "disabled"
    findings_count: int = 0
    enforceable_count: int = 0
    warnings_count: int = 0


class MigrationReadinessBlocker(SceneMigrationReadinessModel):
    fixture_id: str
    profile: str
    category: str
    code: str
    severity: Literal["info", "warning", "error"] = "error"
    enforceable: bool = True
    message: str
    source_report_path: str | None = None
    suggested_next_action: str | None = None


class MigrationReadinessDelta(SceneMigrationReadinessModel):
    fixture_id: str
    metric: str
    previous: int | str | None = None
    current: int | str | None = None
    delta: int | None = None
    status: DeltaStatus = "unavailable"


class FixtureMigrationReadinessSummary(SceneMigrationReadinessModel):
    fixture_id: str
    overall_status: MigrationOverallStatus
    structural_status: str = "missing"
    curated_strict_status: str = "missing"
    visual_smoke_status: str | None = None
    visual_diff_local_status: str | None = None
    visual_diff_pinned_status: str | None = None
    object_status: str = "disabled"
    style_status: str = "disabled"
    adapter_status: str = "disabled"
    screenshot_status: str = "unavailable"
    visual_status: str = "unavailable"
    findings_count: int = 0
    enforceable_count: int = 0
    text_overflow_risk: int = 0
    trace_missing: int = 0
    duplicate_traces: int = 0
    unresolved_style_token_count: int = 0
    fallback_style_count: int = 0
    adapter_findings: int = 0
    unsupported_layout_family_count: int = 0
    placeholder_shape_count: int = 0
    visual_threshold_failures: int = 0
    visual_missing_baselines: int = 0
    remaining_warnings_by_category: dict[str, int] = Field(default_factory=dict)
    profile_statuses: dict[str, ProfileReadinessSummary] = Field(default_factory=dict)
    blockers: list[MigrationReadinessBlocker] = Field(default_factory=list)
    deltas: list[MigrationReadinessDelta] = Field(default_factory=list)


class SceneMigrationReadinessReport(SceneMigrationReadinessModel):
    report_version: str = SCENE_MIGRATION_READINESS_REPORT_VERSION
    generated_from_profiles: list[str]
    fixture_count: int
    fixture_ids: list[str]
    overall_status: MigrationOverallStatus
    nonvisual_ready_count: int
    visual_smoke_ready_count: int
    visual_diff_ready_count: int
    default_migration_recommendation: MigrationRecommendation
    blockers: list[MigrationReadinessBlocker] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    per_fixture: list[FixtureMigrationReadinessSummary] = Field(default_factory=list)
    profile_artifact_paths: dict[str, str] = Field(default_factory=dict)
    previous_report_path: str | None = None
    deltas: list[MigrationReadinessDelta] = Field(default_factory=list)
    structural_hash: str = ""

    def to_stable_payload(self, *, include_paths: bool = True) -> dict[str, Any]:
        return scene_migration_readiness_report_to_stable_payload(self, include_paths=include_paths)

    def to_stable_json(self) -> str:
        return scene_migration_readiness_report_to_stable_json(self)


def load_profile_readiness_report(artifacts_root: str | Path, profile: str) -> dict[str, Any] | None:
    report_path = Path(artifacts_root) / profile / "scene-readiness-report.json"
    if not report_path.is_file():
        return None
    return json.loads(report_path.read_text(encoding="utf-8"))


def build_scene_migration_readiness_report(
    *,
    artifacts_root: str | Path,
    previous_report_path: str | Path | None = None,
) -> SceneMigrationReadinessReport:
    root = Path(artifacts_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"scene readiness artifacts root not found: {root}")

    reports: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    profile_paths: dict[str, str] = {}
    for profile in MIGRATION_PROFILES:
        report = load_profile_readiness_report(root, profile)
        if report is None:
            if profile in REQUIRED_MIGRATION_PROFILES:
                raise FileNotFoundError(f"required scene readiness report not found: {root / profile / 'scene-readiness-report.json'}")
            warnings.append(f"optional profile artifact missing: {profile}")
            continue
        reports[profile] = report
        profile_paths[profile] = str((root / profile / "scene-readiness-report.json").resolve())

    fixture_ids = _fixture_ids_from_reports(reports)
    previous_report = (
        SceneMigrationReadinessReport.model_validate_json(Path(previous_report_path).read_text(encoding="utf-8"))
        if previous_report_path is not None
        else None
    )
    previous_by_fixture = {fixture.fixture_id: fixture for fixture in previous_report.per_fixture} if previous_report else {}

    fixture_summaries: list[FixtureMigrationReadinessSummary] = []
    for fixture_id in fixture_ids:
        summary = _fixture_summary(fixture_id, reports, profile_paths)
        if previous_report is not None:
            summary = summary.model_copy(update={"deltas": _fixture_deltas(summary, previous_by_fixture.get(fixture_id))})
        fixture_summaries.append(summary)

    blockers = [blocker for fixture in fixture_summaries for blocker in fixture.blockers]
    deltas = [delta for fixture in fixture_summaries for delta in fixture.deltas]
    overall_status = _overall_status(fixture_summaries)
    report = SceneMigrationReadinessReport(
        generated_from_profiles=sorted(reports),
        fixture_count=len(fixture_summaries),
        fixture_ids=[fixture.fixture_id for fixture in fixture_summaries],
        overall_status=overall_status,
        nonvisual_ready_count=sum(1 for fixture in fixture_summaries if fixture.overall_status in {"ready_nonvisual", "ready_nonvisual_visual_smoke_available", "ready_with_pinned_visual_evidence"}),
        visual_smoke_ready_count=sum(1 for fixture in fixture_summaries if fixture.visual_smoke_status == "passed"),
        visual_diff_ready_count=sum(1 for fixture in fixture_summaries if fixture.visual_diff_pinned_status == "passed"),
        default_migration_recommendation=_recommendation(overall_status),
        blockers=blockers,
        warnings=warnings,
        per_fixture=fixture_summaries,
        profile_artifact_paths=dict(sorted(profile_paths.items())),
        previous_report_path=str(Path(previous_report_path).resolve()) if previous_report_path is not None else None,
        deltas=deltas,
        structural_hash="",
    )
    return report.model_copy(update={"structural_hash": scene_migration_readiness_report_structural_hash(report)})


def compare_migration_readiness_reports(
    current: SceneMigrationReadinessReport,
    previous: SceneMigrationReadinessReport | None,
) -> list[MigrationReadinessDelta]:
    if previous is None:
        return []
    previous_by_fixture = {fixture.fixture_id: fixture for fixture in previous.per_fixture}
    return [
        delta
        for fixture in current.per_fixture
        for delta in _fixture_deltas(fixture, previous_by_fixture.get(fixture.fixture_id))
    ]


def write_migration_readiness_artifacts(
    report: SceneMigrationReadinessReport,
    *,
    output_path: str | Path,
    markdown_path: str | Path | None = None,
) -> tuple[Path, Path | None]:
    json_path = Path(output_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(scene_migration_readiness_report_to_stable_json(report) + "\n", encoding="utf-8")
    md_path: Path | None = None
    if markdown_path is not None:
        md_path = Path(markdown_path)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(scene_migration_readiness_report_to_markdown(report), encoding="utf-8")
    return json_path, md_path


def scene_migration_readiness_report_to_stable_payload(
    report: SceneMigrationReadinessReport,
    *,
    include_paths: bool = True,
) -> dict[str, Any]:
    payload = report.model_dump(mode="json", exclude_none=True, by_alias=True)
    if not include_paths:
        payload.pop("previous_report_path", None)
        payload.pop("profile_artifact_paths", None)
        for fixture in payload.get("per_fixture", []):
            for profile_summary in fixture.get("profile_statuses", {}).values():
                profile_summary.pop("report_path", None)
            for blocker in fixture.get("blockers", []):
                blocker.pop("source_report_path", None)
        for blocker in payload.get("blockers", []):
            blocker.pop("source_report_path", None)
    return _normalize_for_stable_json(payload)


def scene_migration_readiness_report_to_stable_json(report: SceneMigrationReadinessReport) -> str:
    return json.dumps(
        scene_migration_readiness_report_to_stable_payload(report),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def scene_migration_readiness_report_structural_hash(report: SceneMigrationReadinessReport) -> str:
    payload = scene_migration_readiness_report_to_stable_payload(report, include_paths=False)
    payload.pop("structural_hash", None)
    stable_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


def scene_migration_readiness_report_to_markdown(report: SceneMigrationReadinessReport) -> str:
    lines = [
        "# Scene Migration Readiness",
        "",
        "## Executive Summary",
        "",
        f"- Overall status: `{report.overall_status}`",
        f"- Recommendation: `{report.default_migration_recommendation}`",
        f"- Fixtures: {report.fixture_count}",
        f"- Non-visual ready: {report.nonvisual_ready_count}",
        f"- Visual smoke ready: {report.visual_smoke_ready_count}",
        f"- Pinned visual diff ready: {report.visual_diff_ready_count}",
        "",
        "## Fixture Matrix",
        "",
        "| Fixture | Status | Structural | Curated Strict | Visual Smoke | Visual Pinned | Blockers |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for fixture in report.per_fixture:
        lines.append(
            "| "
            + " | ".join(
                [
                    fixture.fixture_id,
                    fixture.overall_status,
                    fixture.structural_status,
                    fixture.curated_strict_status,
                    fixture.visual_smoke_status or "unavailable",
                    fixture.visual_diff_pinned_status or "unavailable",
                    str(len(fixture.blockers)),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Remaining Blockers", ""])
    if not report.blockers:
        lines.append("No enforced blockers are present in the aggregated readiness artifacts.")
    else:
        for blocker in report.blockers:
            lines.append(f"- `{blocker.fixture_id}` `{blocker.profile}` `{blocker.category}` `{blocker.code}`: {blocker.message}")
    lines.extend(["", "## Visual Evidence", ""])
    if report.visual_smoke_ready_count or report.visual_diff_ready_count:
        lines.append(f"Visual evidence is available for {max(report.visual_smoke_ready_count, report.visual_diff_ready_count)} fixture(s).")
    else:
        lines.append("No optional visual profile evidence was available in the artifact root.")
    if report.deltas:
        lines.extend(["", "## Delta Summary", ""])
        for delta in report.deltas:
            lines.append(f"- `{delta.fixture_id}` `{delta.metric}`: {delta.previous} -> {delta.current} (`{delta.status}`)")
    lines.extend(["", "## Artifact Paths", ""])
    for profile, path in sorted(report.profile_artifact_paths.items()):
        lines.append(f"- `{profile}`: `{path}`")
    return "\n".join(lines) + "\n"


def summarize_scene_migration_readiness_report(report: SceneMigrationReadinessReport) -> list[str]:
    return [
        (
            "SCENE_MIGRATION_READINESS "
            f"status={report.overall_status} "
            f"recommendation={report.default_migration_recommendation} "
            f"fixtures={report.fixture_count} "
            f"nonvisual_ready={report.nonvisual_ready_count} "
            f"visual_smoke_ready={report.visual_smoke_ready_count} "
            f"visual_diff_ready={report.visual_diff_ready_count} "
            f"blockers={len(report.blockers)} "
            f"warnings={len(report.warnings)}"
        )
    ]


def _fixture_ids_from_reports(reports: dict[str, dict[str, Any]]) -> list[str]:
    fixture_ids: set[str] = set()
    for report in reports.values():
        for fixture in report.get("fixtures", []):
            fixture_id = fixture.get("fixture_id")
            if isinstance(fixture_id, str):
                fixture_ids.add(fixture_id)
    return sorted(fixture_ids)


def _fixture_summary(
    fixture_id: str,
    reports: dict[str, dict[str, Any]],
    profile_paths: dict[str, str],
) -> FixtureMigrationReadinessSummary:
    profile_summaries = {
        profile: _profile_summary_for_fixture(profile, reports.get(profile), profile_paths.get(profile), fixture_id)
        for profile in MIGRATION_PROFILES
        if profile in reports
    }
    structural = profile_summaries.get("structural")
    curated = profile_summaries.get("curated-strict")
    visual_smoke = profile_summaries.get("visual-smoke")
    visual_local = profile_summaries.get("visual-diff-local")
    visual_pinned = profile_summaries.get("visual-diff-pinned")
    curated_fixture = _fixture_by_id(reports.get("curated-strict", {}), fixture_id) or {}
    structural_fixture = _fixture_by_id(reports.get("structural", {}), fixture_id) or {}
    visual_fixture = _fixture_by_id(reports.get("visual-diff-pinned", {}), fixture_id) or _fixture_by_id(reports.get("visual-diff-local", {}), fixture_id) or _fixture_by_id(reports.get("visual-smoke", {}), fixture_id) or {}
    blockers = _blockers_for_fixture(fixture_id, reports, profile_paths)
    warnings_by_category = Counter()
    adapter_summary = curated_fixture.get("adapter_quality_summary") or {}
    for code, count in dict(adapter_summary.get("adapter_warning_count_by_code", {})).items():
        warnings_by_category[f"adapter:{code}"] += int(count)
    summary = FixtureMigrationReadinessSummary(
        fixture_id=fixture_id,
        overall_status="insufficient_evidence",
        structural_status=structural.status if structural else "missing",
        curated_strict_status=curated.status if curated else "missing",
        visual_smoke_status=visual_smoke.status if visual_smoke else None,
        visual_diff_local_status=visual_local.status if visual_local else None,
        visual_diff_pinned_status=visual_pinned.status if visual_pinned else None,
        object_status=str(curated_fixture.get("object_validation_status") or structural_fixture.get("object_validation_status") or "disabled"),
        style_status=str(curated_fixture.get("style_policy_status") or "disabled"),
        adapter_status=str(curated_fixture.get("adapter_policy_status") or "disabled"),
        screenshot_status=str(visual_fixture.get("screenshot_export_status") or "unavailable"),
        visual_status=str(visual_fixture.get("visual_comparison_status") or "unavailable"),
        findings_count=sum(profile.findings_count for profile in profile_summaries.values()),
        enforceable_count=sum(profile.enforceable_count for profile in profile_summaries.values()),
        text_overflow_risk=int(curated_fixture.get("text_overflow_risk_count") or structural_fixture.get("text_overflow_risk_count") or 0),
        trace_missing=int(curated_fixture.get("trace_missing_count") or structural_fixture.get("trace_missing_count") or 0),
        duplicate_traces=int(curated_fixture.get("duplicate_trace_count") or structural_fixture.get("duplicate_trace_count") or 0),
        unresolved_style_token_count=int(curated_fixture.get("unresolved_theme_token_count") or 0)
        + int(curated_fixture.get("unresolved_font_token_count") or 0)
        + int(curated_fixture.get("unresolved_spacing_token_count") or 0),
        fallback_style_count=int(curated_fixture.get("fallback_style_count") or 0),
        adapter_findings=int(curated_fixture.get("adapter_policy_enforceable_count") or 0),
        unsupported_layout_family_count=int(adapter_summary.get("unsupported_layout_family_count") or 0),
        placeholder_shape_count=int(adapter_summary.get("placeholder_shape_count") or 0),
        visual_threshold_failures=int(visual_fixture.get("visual_threshold_failure_count") or 0),
        visual_missing_baselines=int(visual_fixture.get("visual_missing_baseline_count") or 0),
        remaining_warnings_by_category=dict(sorted(warnings_by_category.items())),
        profile_statuses=profile_summaries,
        blockers=blockers,
    )
    return summary.model_copy(update={"overall_status": _classify_fixture(summary)})


def _profile_summary_for_fixture(
    profile: str,
    report: dict[str, Any] | None,
    report_path: str | None,
    fixture_id: str,
) -> ProfileReadinessSummary:
    if report is None:
        return ProfileReadinessSummary(profile=profile, available=False)
    fixture = _fixture_by_id(report, fixture_id) or {}
    return ProfileReadinessSummary(
        profile=profile,
        available=True,
        report_path=report_path,
        status=str(fixture.get("status") or report.get("mode_result") or "missing"),
        readiness_profile=str(report.get("readiness_profile") or profile),
        object_status=str(fixture.get("object_validation_status") or report.get("object_validation_status") or "disabled"),
        style_status=str(fixture.get("style_policy_status") or report.get("style_policy_status") or "disabled"),
        adapter_status=str(fixture.get("adapter_policy_status") or report.get("adapter_policy_status") or "disabled"),
        screenshot_status=str(fixture.get("screenshot_export_status") or report.get("screenshot_export_status") or "disabled"),
        visual_status=str(fixture.get("visual_comparison_status") or report.get("visual_comparison_status") or "disabled"),
        findings_count=int(fixture.get("validator_finding_count") or 0)
        + len(fixture.get("style_policy_findings") or [])
        + len(fixture.get("adapter_policy_findings") or [])
        + int(fixture.get("screenshot_finding_count") or 0)
        + int(fixture.get("visual_finding_count") or 0),
        enforceable_count=int(fixture.get("combined_nonvisual_enforceable_count") or 0)
        + int(fixture.get("screenshot_error_count") or 0)
        + int(fixture.get("visual_error_count") or 0),
        warnings_count=int(fixture.get("adapter_warning_count") or 0)
        + int(fixture.get("compile_warning_count") or 0)
        + int(fixture.get("screenshot_warning_count") or 0)
        + int(fixture.get("visual_warning_count") or 0),
    )


def _fixture_by_id(report: dict[str, Any], fixture_id: str) -> dict[str, Any] | None:
    for fixture in report.get("fixtures", []):
        if fixture.get("fixture_id") == fixture_id:
            return fixture
    return None


def _classify_fixture(summary: FixtureMigrationReadinessSummary) -> MigrationOverallStatus:
    if summary.structural_status != "passed":
        return "blocked_structural"
    if summary.curated_strict_status != "passed":
        if summary.style_status == "failed":
            return "blocked_style"
        if summary.adapter_status == "failed":
            return "blocked_adapter"
        if summary.object_status == "failed":
            return "blocked_structural"
        return "insufficient_evidence"
    if summary.visual_diff_pinned_status == "failed" or summary.visual_diff_local_status == "failed":
        return "blocked_visual"
    if summary.visual_threshold_failures > 0 or summary.visual_status == "failed":
        return "blocked_visual"
    if summary.visual_diff_pinned_status == "passed":
        return "ready_with_pinned_visual_evidence"
    if summary.visual_smoke_status == "passed":
        return "ready_nonvisual_visual_smoke_available"
    if summary.visual_smoke_status == "failed":
        return "blocked_visual"
    return "ready_nonvisual"


def _overall_status(fixtures: list[FixtureMigrationReadinessSummary]) -> MigrationOverallStatus:
    if not fixtures:
        return "insufficient_evidence"
    statuses = [fixture.overall_status for fixture in fixtures]
    for blocked in ("blocked_structural", "blocked_style", "blocked_adapter", "blocked_visual", "insufficient_evidence"):
        if blocked in statuses:
            return blocked  # type: ignore[return-value]
    if all(status == "ready_with_pinned_visual_evidence" for status in statuses):
        return "ready_with_pinned_visual_evidence"
    if any(status == "ready_nonvisual_visual_smoke_available" for status in statuses):
        return "ready_nonvisual_visual_smoke_available"
    return "ready_nonvisual"


def _recommendation(status: MigrationOverallStatus) -> MigrationRecommendation:
    if status in {"blocked_structural", "blocked_style", "blocked_adapter", "blocked_visual"}:
        return "no_go"
    if status == "insufficient_evidence":
        return "not_yet"
    if status == "ready_nonvisual":
        return "ready_for_limited_default_path_poc"
    if status == "ready_nonvisual_visual_smoke_available":
        return "ready_for_default_path_migration_discussion"
    return "ready_for_visual_pinned_review"


def _blockers_for_fixture(
    fixture_id: str,
    reports: dict[str, dict[str, Any]],
    profile_paths: dict[str, str],
) -> list[MigrationReadinessBlocker]:
    blockers: list[MigrationReadinessBlocker] = []
    for profile in REQUIRED_MIGRATION_PROFILES:
        if profile not in reports:
            blockers.append(_blocker(fixture_id, profile, "missing_artifact", "required_profile_missing", f"Required readiness profile artifact is missing: {profile}", None))
    for profile, report in reports.items():
        fixture = _fixture_by_id(report, fixture_id)
        if fixture is None:
            blockers.append(_blocker(fixture_id, profile, "missing_artifact", "fixture_missing_in_profile", f"Fixture is missing from profile report: {profile}", profile_paths.get(profile)))
            continue
        if fixture.get("execution_error"):
            blockers.append(_blocker(fixture_id, profile, "fixture_instability", "fixture_execution_error", str(fixture["execution_error"]), profile_paths.get(profile)))
        if profile in {"structural", "curated-strict"}:
            if fixture.get("object_validation_status") == "failed" or fixture.get("validator_mode_result") == "failed":
                blockers.append(_blocker(fixture_id, profile, "object_validation", "object_validation_failed", "Scene-strict PPTX object validation failed.", profile_paths.get(profile), "Inspect pptx-object-report.json for trace/editability findings."))
            if int(fixture.get("text_overflow_risk_count") or 0) > 0:
                blockers.append(_blocker(fixture_id, profile, "text_fit", "text_overflow_risk", "Text overflow risk remains in scene validation.", profile_paths.get(profile), "Inspect text-fit diagnostics."))
            if int(fixture.get("trace_missing_count") or 0) > 0 or int(fixture.get("duplicate_trace_count") or 0) > 0:
                blockers.append(_blocker(fixture_id, profile, "trace_consistency", "trace_consistency_failed", "Trace consistency findings remain.", profile_paths.get(profile)))
        if profile == "curated-strict":
            for finding in fixture.get("style_policy_findings") or []:
                blockers.append(_blocker(fixture_id, profile, "style_policy", str(finding.get("code", "style_policy_finding")), str(finding.get("message", "Style policy finding.")), profile_paths.get(profile)))
            for finding in fixture.get("adapter_policy_findings") or []:
                blockers.append(_blocker(fixture_id, profile, "adapter_policy", str(finding.get("code", "adapter_policy_finding")), str(finding.get("message", "Adapter policy finding.")), profile_paths.get(profile)))
        if profile.startswith("visual"):
            if fixture.get("screenshot_export_status") in {"failed", "unavailable"}:
                blockers.append(_blocker(fixture_id, profile, "screenshot_export", "screenshot_export_not_passed", "Screenshot export did not pass for optional visual evidence.", profile_paths.get(profile), enforceable=False))
            if fixture.get("visual_comparison_status") == "failed" or int(fixture.get("visual_threshold_failure_count") or 0) > 0:
                blockers.append(_blocker(fixture_id, profile, "visual_regression", "visual_regression_failed", "Visual regression evidence failed.", profile_paths.get(profile)))
    return sorted(blockers, key=lambda item: (item.fixture_id, item.profile, item.category, item.code))


def _blocker(
    fixture_id: str,
    profile: str,
    category: str,
    code: str,
    message: str,
    source_report_path: str | None,
    suggested_next_action: str | None = None,
    *,
    enforceable: bool = True,
) -> MigrationReadinessBlocker:
    return MigrationReadinessBlocker(
        fixture_id=fixture_id,
        profile=profile,
        category=category,
        code=code,
        severity="error" if enforceable else "warning",
        enforceable=enforceable,
        message=message,
        source_report_path=source_report_path,
        suggested_next_action=suggested_next_action,
    )


def _fixture_deltas(
    current: FixtureMigrationReadinessSummary,
    previous: FixtureMigrationReadinessSummary | None,
) -> list[MigrationReadinessDelta]:
    metrics = {
        "findings_count": current.findings_count,
        "enforceable_count": current.enforceable_count,
        "text_overflow_risk": current.text_overflow_risk,
        "trace_missing": current.trace_missing,
        "unresolved_style_token_count": current.unresolved_style_token_count,
        "fallback_style_count": current.fallback_style_count,
        "adapter_findings": current.adapter_findings,
        "placeholder_shape_count": current.placeholder_shape_count,
        "unsupported_layout_family_count": current.unsupported_layout_family_count,
        "visual_threshold_failures": current.visual_threshold_failures,
        "visual_missing_baselines": current.visual_missing_baselines,
    }
    deltas: list[MigrationReadinessDelta] = []
    for metric, current_value in metrics.items():
        previous_value = getattr(previous, metric) if previous is not None else None
        if previous_value is None:
            deltas.append(MigrationReadinessDelta(fixture_id=current.fixture_id, metric=metric, current=current_value, status="unavailable"))
            continue
        delta = int(current_value) - int(previous_value)
        status: DeltaStatus = "unchanged"
        if delta < 0:
            status = "improved"
        elif delta > 0:
            status = "regressed"
        deltas.append(
            MigrationReadinessDelta(
                fixture_id=current.fixture_id,
                metric=metric,
                previous=int(previous_value),
                current=int(current_value),
                delta=delta,
                status=status,
            )
        )
    if previous is not None and previous.overall_status != current.overall_status:
        deltas.append(
            MigrationReadinessDelta(
                fixture_id=current.fixture_id,
                metric="overall_status",
                previous=previous.overall_status,
                current=current.overall_status,
                status="regressed" if current.overall_status.startswith("blocked") else "improved",
            )
        )
    return deltas


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
