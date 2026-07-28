"""CI-oriented wrapper for the opt-in SceneDeck readiness gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..pipeline.pptx_screenshot_export import (
    ScreenshotExportImplementation,
    ScreenshotExporterDetection,
)
from ..pipeline.scene_readiness_gate import (
    ReadinessProfile,
    SceneReadinessReport,
    run_scene_readiness_gate_from_file,
    scene_readiness_report_structural_hash,
    summarize_scene_readiness_report,
    write_scene_readiness_report,
)
from ..pipeline.scene_migration_readiness import (
    build_scene_migration_readiness_report,
    summarize_scene_migration_readiness_report,
    write_migration_readiness_artifacts,
)
from ..pipeline.scene_migration_history import (
    build_scene_migration_history,
    summarize_scene_migration_history_report,
    write_scene_migration_history_artifacts,
)
from ..pipeline.scene_default_comparison import (
    run_default_vs_scene_poc,
    summarize_default_vs_scene_report,
)
from ..pipeline.experimental_scene_compile import (
    compile_experimental_scene_renderer_from_manifest,
    experimental_scene_compile_failed,
    summarize_experimental_scene_compile,
)
from ..pipeline.flagged_scene_compile_check import (
    flagged_scene_compile_check_failed,
    run_flagged_scene_compile_check,
    summarize_flagged_scene_compile_check,
)


SCENE_READINESS_CI_SUMMARY_VERSION = "0.4"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = REPO_ROOT / "tests" / "fixtures" / "scene_gate" / "scene-gate-fixtures.json"
DEFAULT_VISUAL_POLICY_PATH = REPO_ROOT / "tests" / "fixtures" / "scene_gate" / "visual-baseline-policy.json"
DEFAULT_STYLE_POLICY_PATH = REPO_ROOT / "tests" / "fixtures" / "scene_gate" / "scene-style-policy.json"
DEFAULT_ADAPTER_POLICY_PATH = REPO_ROOT / "tests" / "fixtures" / "scene_gate" / "scene-adapter-policy.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "scene-readiness"
DEFAULT_MIGRATION_DASHBOARD_OUTPUT = REPO_ROOT / "artifacts" / "scene-readiness-dashboard"
DEFAULT_MIGRATION_HISTORY_OUTPUT = REPO_ROOT / "artifacts" / "scene-migration-history"
DEFAULT_DEFAULT_VS_SCENE_OUTPUT = REPO_ROOT / "artifacts" / "default-vs-scene-poc"
DEFAULT_FLAGGED_SCENE_COMPILE_OUTPUT = REPO_ROOT / "artifacts" / "flagged-scene-compile"
DEFAULT_FLAGGED_SCENE_COMPILE_CHECK_OUTPUT = REPO_ROOT / "artifacts" / "flagged-scene-compile-check"
READINESS_CI_PROFILES: tuple[ReadinessProfile, ...] = (
    "structural",
    "style-strict",
    "adapter-strict",
    "curated-strict",
    "visual-smoke",
    "visual-diff-local",
    "visual-diff-pinned",
    "baseline-refresh",
)
READINESS_CI_COMMANDS: tuple[str, ...] = (
    *READINESS_CI_PROFILES,
    "migration-dashboard",
    "migration-history",
    "default-vs-scene-poc",
    "flagged-scene-compile",
    "flagged-scene-compile-check",
)


class SceneReadinessCiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SceneReadinessCiSummary(SceneReadinessCiModel):
    wrapper_version: str = SCENE_READINESS_CI_SUMMARY_VERSION
    selected_profile: ReadinessProfile
    manifest_path: str
    visual_policy_path: str
    style_policy_path: str | None = None
    adapter_policy_path: str | None = None
    output_dir: str
    visual_baseline_dir: str | None = None
    fixture_ids: list[str] = Field(default_factory=list)
    normalized_options: dict[str, Any] = Field(default_factory=dict)
    scene_readiness_report_path: str
    scene_readiness_report_hash: str
    structural_hash: str
    overall_status: str
    fixture_count: int
    passed_count: int
    failed_count: int
    findings_count: int
    warnings_count: int
    object_status: str = "disabled"
    combined_nonvisual_status: str = "disabled"
    combined_nonvisual_findings: int = 0
    combined_nonvisual_enforceable: int = 0
    text_overflow_risk: int = 0
    trace_missing: int = 0
    adapter_status: str = "disabled"
    adapter_findings: int = 0
    adapter_enforceable: int = 0
    adapter_warnings: int = 0
    placeholder_shape_count: int = 0
    unsupported_layout_family_count: int = 0
    style_warning_count: int = 0
    unresolved_theme_token_count: int = 0
    unresolved_font_token_count: int = 0
    unresolved_spacing_token_count: int = 0
    fallback_style_count: int = 0
    style_alias_count: int = 0
    deprecated_style_alias_count: int = 0
    ambiguous_style_alias_count: int = 0
    style_status: str = "disabled"
    style_findings: int = 0
    style_enforceable: int = 0
    unresolved_style_tokens: int = 0
    screenshot_status: str | None = None
    visual_status: str | None = None
    visual_threshold_failures: int = 0
    missing_baselines: int = 0
    baseline_refresh_count: int = 0

    def to_stable_payload(self, *, include_paths: bool = True) -> dict[str, Any]:
        return scene_readiness_ci_summary_to_stable_payload(self, include_paths=include_paths)

    def to_stable_json(self) -> str:
        return scene_readiness_ci_summary_to_stable_json(self)


@dataclass(frozen=True)
class SceneReadinessCiOutputs:
    report: SceneReadinessReport
    summary: SceneReadinessCiSummary
    report_path: Path
    summary_path: Path


def run_scene_readiness_ci(
    *,
    profile: ReadinessProfile = "structural",
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    visual_policy_path: str | Path = DEFAULT_VISUAL_POLICY_PATH,
    style_policy_path: str | Path | None = DEFAULT_STYLE_POLICY_PATH,
    adapter_policy_path: str | Path | None = DEFAULT_ADAPTER_POLICY_PATH,
    output_dir: str | Path | None = None,
    visual_baseline_dir: str | Path | None = None,
    fixture_ids: list[str] | None = None,
    write_diff_images: bool | None = None,
    screenshot_export_impl: ScreenshotExportImplementation | None = None,
    screenshot_detection_override: ScreenshotExporterDetection | None = None,
) -> SceneReadinessCiOutputs:
    manifest_file = Path(manifest_path).resolve()
    visual_policy_file = Path(visual_policy_path).resolve()
    style_policy_file = Path(style_policy_path).resolve() if style_policy_path is not None else None
    adapter_policy_file = Path(adapter_policy_path).resolve() if adapter_policy_path is not None else None
    output_root = Path(output_dir).resolve() if output_dir is not None else (DEFAULT_OUTPUT_ROOT / profile).resolve()
    baseline_root = Path(visual_baseline_dir).resolve() if visual_baseline_dir is not None else None

    _validate_ci_inputs(
        profile=profile,
        manifest_path=manifest_file,
        visual_policy_path=visual_policy_file,
        style_policy_path=style_policy_file,
        adapter_policy_path=adapter_policy_file,
        visual_baseline_dir=baseline_root,
    )
    gate_options = _gate_options_for_profile(profile, write_diff_images=write_diff_images)
    output_root.mkdir(parents=True, exist_ok=True)
    report = run_scene_readiness_gate_from_file(
        manifest_path=manifest_file,
        output_dir=output_root,
        fixture_ids=fixture_ids,
        visual_policy_path=visual_policy_file,
        style_policy_path=style_policy_file,
        adapter_policy_path=adapter_policy_file,
        visual_baseline_dir=baseline_root,
        screenshot_export_impl=screenshot_export_impl,
        screenshot_detection_override=screenshot_detection_override,
        **gate_options,
    )
    report_path = write_scene_readiness_report(report, output_root / "scene-readiness-report.json")
    normalized_options = {
        "fixture_ids": sorted(fixture_ids or []),
        "profile": profile,
        "visual_baseline_dir_required": _profile_requires_baseline_dir(profile),
        **gate_options,
    }
    summary = build_scene_readiness_ci_summary(
        report,
        selected_profile=profile,
        manifest_path=manifest_file,
        visual_policy_path=visual_policy_file,
        style_policy_path=style_policy_file,
        adapter_policy_path=adapter_policy_file,
        output_dir=output_root,
        visual_baseline_dir=baseline_root,
        fixture_ids=fixture_ids or [],
        normalized_options=normalized_options,
        report_path=report_path,
    )
    summary_path = write_scene_readiness_ci_summary(summary, output_root / "scene-readiness-ci-summary.json")
    return SceneReadinessCiOutputs(report=report, summary=summary, report_path=report_path, summary_path=summary_path)


def build_scene_readiness_ci_summary(
    report: SceneReadinessReport,
    *,
    selected_profile: ReadinessProfile,
    manifest_path: Path,
    visual_policy_path: Path,
    style_policy_path: Path | None = None,
    adapter_policy_path: Path | None = None,
    output_dir: Path,
    visual_baseline_dir: Path | None,
    fixture_ids: list[str],
    normalized_options: dict[str, Any],
    report_path: Path,
) -> SceneReadinessCiSummary:
    warnings_count = (
        report.adapter_warning_count
        + report.compile_warning_count
        + report.screenshot_warning_count
        + report.visual_warning_count
    )
    findings_count = (
        report.validator_finding_count
        + report.style_policy_finding_count
        + report.adapter_policy_finding_count
        + report.screenshot_finding_count
        + report.visual_finding_count
    )
    summary = SceneReadinessCiSummary(
        selected_profile=selected_profile,
        manifest_path=str(manifest_path),
        visual_policy_path=str(visual_policy_path),
        style_policy_path=str(style_policy_path) if style_policy_path is not None else None,
        adapter_policy_path=str(adapter_policy_path) if adapter_policy_path is not None else None,
        output_dir=str(output_dir),
        visual_baseline_dir=str(visual_baseline_dir) if visual_baseline_dir is not None else None,
        fixture_ids=sorted(fixture_ids),
        normalized_options=_normalize_for_stable_json(normalized_options),
        scene_readiness_report_path=str(report_path),
        scene_readiness_report_hash=scene_readiness_report_structural_hash(report),
        structural_hash="",
        overall_status=report.mode_result,
        fixture_count=report.fixture_count,
        passed_count=report.passed_fixture_count,
        failed_count=report.failed_fixture_count,
        findings_count=findings_count,
        warnings_count=warnings_count,
        object_status=report.object_validation_status,
        combined_nonvisual_status=report.combined_nonvisual_status,
        combined_nonvisual_findings=report.combined_nonvisual_findings,
        combined_nonvisual_enforceable=report.combined_nonvisual_enforceable_count,
        text_overflow_risk=report.text_overflow_risk_count,
        trace_missing=report.trace_missing_count,
        adapter_status=report.adapter_policy_status,
        adapter_findings=report.adapter_policy_finding_count,
        adapter_enforceable=report.adapter_policy_enforceable_count,
        adapter_warnings=report.adapter_warning_count,
        placeholder_shape_count=report.adapter_quality_summary.placeholder_shape_count,
        unsupported_layout_family_count=report.adapter_quality_summary.unsupported_layout_family_count,
        style_warning_count=report.style_warning_count,
        unresolved_theme_token_count=report.unresolved_theme_token_count,
        unresolved_font_token_count=report.unresolved_font_token_count,
        unresolved_spacing_token_count=report.unresolved_spacing_token_count,
        fallback_style_count=report.fallback_style_count,
        style_alias_count=report.style_alias_count,
        deprecated_style_alias_count=report.deprecated_style_alias_count,
        ambiguous_style_alias_count=report.ambiguous_style_alias_count,
        style_status=report.style_policy_status,
        style_findings=report.style_policy_finding_count,
        style_enforceable=report.style_policy_enforceable_count,
        unresolved_style_tokens=(
            report.unresolved_theme_token_count
            + report.unresolved_font_token_count
            + report.unresolved_spacing_token_count
        ),
        screenshot_status=report.screenshot_export_status if report.screenshots_enabled else None,
        visual_status=report.visual_comparison_status if report.visual_diff_enabled else None,
        visual_threshold_failures=report.visual_threshold_failure_count,
        missing_baselines=report.visual_missing_baseline_count,
        baseline_refresh_count=report.baseline_refresh_count,
    )
    return summary.model_copy(update={"structural_hash": scene_readiness_ci_summary_structural_hash(summary)})


def write_scene_readiness_ci_summary(summary: SceneReadinessCiSummary, output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(scene_readiness_ci_summary_to_stable_json(summary) + "\n", encoding="utf-8")
    return destination


def summarize_scene_readiness_ci_outputs(outputs: SceneReadinessCiOutputs) -> list[str]:
    summary = outputs.summary
    header = (
        "SCENE_READINESS_CI "
        f"profile={summary.selected_profile} "
        f"status={summary.overall_status} "
        f"fixtures={summary.fixture_count} "
        f"passed={summary.passed_count} "
        f"failed={summary.failed_count} "
        f"warnings={summary.warnings_count} "
        f"object_status={summary.object_status} "
        f"combined_nonvisual_status={summary.combined_nonvisual_status} "
        f"combined_nonvisual_enforceable={summary.combined_nonvisual_enforceable} "
        f"adapter_status={summary.adapter_status} "
        f"adapter_findings={summary.adapter_findings} "
        f"adapter_enforceable={summary.adapter_enforceable} "
        f"style_warnings={summary.style_warning_count} "
        f"style_aliases={summary.style_alias_count} "
        f"style_status={summary.style_status} "
        f"style_findings={summary.style_findings} "
        f"style_enforceable={summary.style_enforceable} "
        f"findings={summary.findings_count}"
    )
    if summary.screenshot_status is not None:
        header += f" screenshot_status={summary.screenshot_status}"
    if summary.visual_status is not None:
        header += (
            f" visual_status={summary.visual_status} "
            f"visual_threshold_failures={summary.visual_threshold_failures} "
            f"visual_missing_baselines={summary.missing_baselines}"
        )
    if summary.baseline_refresh_count:
        header += f" baselines_updated={summary.baseline_refresh_count}"
    return [header, *summarize_scene_readiness_report(outputs.report), f"WROTE {outputs.summary_path}"]


def scene_readiness_ci_summary_to_stable_payload(
    summary: SceneReadinessCiSummary,
    *,
    include_paths: bool = True,
) -> dict[str, Any]:
    payload = summary.model_dump(mode="json", exclude_none=True, by_alias=True)
    if not include_paths:
        for key in (
            "manifest_path",
            "visual_policy_path",
            "style_policy_path",
            "adapter_policy_path",
            "output_dir",
            "visual_baseline_dir",
            "scene_readiness_report_path",
        ):
            payload.pop(key, None)
    return _normalize_for_stable_json(payload)


def scene_readiness_ci_summary_to_stable_json(summary: SceneReadinessCiSummary) -> str:
    return json.dumps(
        scene_readiness_ci_summary_to_stable_payload(summary),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def scene_readiness_ci_summary_structural_hash(summary: SceneReadinessCiSummary) -> str:
    payload = scene_readiness_ci_summary_to_stable_payload(summary, include_paths=False)
    payload.pop("structural_hash", None)
    stable_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run opt-in SceneDeck readiness profiles with CI-safe defaults.",
    )
    parser.add_argument("profile", nargs="?", choices=READINESS_CI_COMMANDS, default="structural")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--visual-policy", dest="visual_policy", type=Path, default=DEFAULT_VISUAL_POLICY_PATH)
    parser.add_argument("--style-policy", dest="style_policy", type=Path, default=DEFAULT_STYLE_POLICY_PATH)
    parser.add_argument("--adapter-policy", dest="adapter_policy", type=Path, default=DEFAULT_ADAPTER_POLICY_PATH)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--visual-baseline-dir", dest="visual_baseline_dir", type=Path)
    parser.add_argument("--artifacts-root", type=Path)
    parser.add_argument("--current-report", type=Path)
    parser.add_argument("--dashboard-dir", type=Path)
    parser.add_argument("--previous-report", type=Path)
    parser.add_argument("--write-markdown", action="store_true")
    parser.add_argument("--fixture", action="append", dest="fixture_ids")
    parser.add_argument(
        "--no-write-diff-images",
        action="store_true",
        help="Disable per-slide visual diff image artifacts for visual diff profiles.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.profile == "migration-dashboard":
        try:
            if args.artifacts_root is None:
                raise ValueError("migration-dashboard requires --artifacts-root")
            output_dir = (args.output_dir or DEFAULT_MIGRATION_DASHBOARD_OUTPUT).resolve()
            report = build_scene_migration_readiness_report(
                artifacts_root=args.artifacts_root,
                previous_report_path=args.previous_report,
            )
            report_path, markdown_path = write_migration_readiness_artifacts(
                report,
                output_path=output_dir / "scene-migration-readiness-report.json",
                markdown_path=(output_dir / "scene-migration-readiness.md") if args.write_markdown else None,
            )
        except Exception as exc:
            print(f"SCENE_READINESS_CI_ERROR {exc}")
            return 2
        for line in summarize_scene_migration_readiness_report(report):
            print(line)
        print(f"WROTE {report_path}")
        if markdown_path is not None:
            print(f"WROTE {markdown_path}")
        return 1 if report.default_migration_recommendation in {"no_go", "not_yet"} else 0
    if args.profile == "migration-history":
        try:
            current_report = args.current_report
            if current_report is None and args.dashboard_dir is not None:
                current_report = args.dashboard_dir / "scene-migration-readiness-report.json"
            if current_report is None:
                raise ValueError("migration-history requires --current-report or --dashboard-dir")
            output_dir = (args.output_dir or DEFAULT_MIGRATION_HISTORY_OUTPUT).resolve()
            report = build_scene_migration_history(
                current_report_path=current_report,
                previous_report_path=args.previous_report,
            )
            report, report_path, markdown_path = write_scene_migration_history_artifacts(
                report,
                output_path=output_dir / "scene-migration-history-report.json",
                markdown_path=(output_dir / "scene-migration-readiness-release-note.md") if args.write_markdown else None,
            )
        except Exception as exc:
            print(f"SCENE_READINESS_CI_ERROR {exc}")
            return 2
        for line in summarize_scene_migration_history_report(report):
            print(line)
        print(f"WROTE {report_path}")
        if markdown_path is not None:
            print(f"WROTE {markdown_path}")
        return 0
    if args.profile == "default-vs-scene-poc":
        try:
            output_dir = (args.output_dir or DEFAULT_DEFAULT_VS_SCENE_OUTPUT).resolve()
            report = run_default_vs_scene_poc(
                manifest_path=args.manifest,
                output_dir=output_dir,
                style_policy_path=args.style_policy,
                adapter_policy_path=args.adapter_policy,
                fixture_ids=args.fixture_ids,
                write_markdown=args.write_markdown,
            )
        except Exception as exc:
            print(f"SCENE_READINESS_CI_ERROR {exc}")
            return 2
        for line in summarize_default_vs_scene_report(report):
            print(line)
        print(f"WROTE {output_dir / 'default-vs-scene-report.json'}")
        if args.write_markdown:
            print(f"WROTE {output_dir / 'default-vs-scene-summary.md'}")
        return 1 if report.recommendation in {"no_go", "not_yet"} else 0
    if args.profile == "flagged-scene-compile":
        try:
            if args.fixture_ids and len(args.fixture_ids) > 1:
                raise ValueError("flagged-scene-compile accepts at most one --fixture")
            output_dir = (args.output_dir or DEFAULT_FLAGGED_SCENE_COMPILE_OUTPUT).resolve()
            outputs = compile_experimental_scene_renderer_from_manifest(
                manifest_path=args.manifest,
                output_dir=output_dir,
                fixture_id=args.fixture_ids[0] if args.fixture_ids else None,
                style_policy_path=args.style_policy,
                adapter_policy_path=args.adapter_policy,
                scene_validate=True,
                scene_profile="curated-strict",
                scene_validation_mode="enforce",
            )
        except Exception as exc:
            print(f"SCENE_READINESS_CI_ERROR {exc}")
            return 2
        for line in summarize_experimental_scene_compile(outputs):
            print(line)
        print(f"WROTE {outputs.scene_outputs.pptx_path}")
        print(f"WROTE {output_dir / 'experimental-scene-compile-report.json'}")
        return 1 if experimental_scene_compile_failed(outputs.report) else 0
    if args.profile == "flagged-scene-compile-check":
        try:
            if args.fixture_ids and len(args.fixture_ids) > 1:
                raise ValueError("flagged-scene-compile-check accepts at most one --fixture")
            output_dir = (args.output_dir or DEFAULT_FLAGGED_SCENE_COMPILE_CHECK_OUTPUT).resolve()
            outputs = run_flagged_scene_compile_check(
                manifest_path=args.manifest,
                output_dir=output_dir,
                fixture_id=args.fixture_ids[0] if args.fixture_ids else None,
                style_policy_path=args.style_policy,
                adapter_policy_path=args.adapter_policy,
            )
        except Exception as exc:
            print(f"SCENE_READINESS_CI_ERROR {exc}")
            return 2
        for line in summarize_flagged_scene_compile_check(outputs):
            print(line)
        print(f"WROTE {outputs.summary_path}")
        print(f"WROTE {Path(outputs.compile_outputs.report_path).resolve()}")
        return 1 if flagged_scene_compile_check_failed(outputs.summary) else 0
    try:
        outputs = run_scene_readiness_ci(
            profile=args.profile,
            manifest_path=args.manifest,
            visual_policy_path=args.visual_policy,
            style_policy_path=args.style_policy,
            adapter_policy_path=args.adapter_policy,
            output_dir=args.output_dir,
            visual_baseline_dir=args.visual_baseline_dir,
            fixture_ids=args.fixture_ids,
            write_diff_images=False if args.no_write_diff_images else None,
        )
    except Exception as exc:
        print(f"SCENE_READINESS_CI_ERROR {exc}")
        return 2
    for line in summarize_scene_readiness_ci_outputs(outputs):
        print(line)
    return 1 if outputs.report.mode_result == "failed" else 0


def _gate_options_for_profile(profile: ReadinessProfile, *, write_diff_images: bool | None) -> dict[str, Any]:
    options: dict[str, Any] = {
        "mode": "enforce",
        "profile": profile,
        "screenshots": False,
        "screenshot_mode": "inspect",
        "screenshot_exporter": "auto",
        "screenshot_output_format": "png",
        "visual_diff": False,
        "update_visual_baselines_flag": False,
        "visual_mode": "inspect",
        "visual_threshold": "default",
        "require_visual_baselines": False,
        "write_diff_images": False,
    }
    if profile == "visual-smoke":
        options["screenshots"] = True
    elif profile == "style-strict":
        options.update(
            {
                "enforce_style_policy": True,
                "style_profile": "style-strict",
            }
        )
    elif profile == "adapter-strict":
        options.update(
            {
                "enforce_adapter_policy": True,
                "adapter_profile": "adapter-strict",
            }
        )
    elif profile == "curated-strict":
        options.update(
            {
                "enforce_style_policy": True,
                "style_profile": "style-strict",
                "enforce_adapter_policy": True,
                "adapter_profile": "adapter-strict",
            }
        )
    elif profile == "visual-diff-local":
        options.update(
            {
                "screenshots": True,
                "visual_diff": True,
                "write_diff_images": True,
            }
        )
    elif profile == "visual-diff-pinned":
        options.update(
            {
                "screenshots": True,
                "screenshot_mode": "enforce",
                "screenshot_exporter": "powerpoint",
                "visual_diff": True,
                "visual_mode": "enforce",
                "require_visual_baselines": True,
                "write_diff_images": True,
            }
        )
    elif profile == "baseline-refresh":
        options.update(
            {
                "screenshots": True,
                "update_visual_baselines_flag": True,
            }
        )
    if write_diff_images is not None:
        options["write_diff_images"] = write_diff_images
    return options


def _validate_ci_inputs(
    *,
    profile: ReadinessProfile,
    manifest_path: Path,
    visual_policy_path: Path,
    style_policy_path: Path | None = None,
    adapter_policy_path: Path | None = None,
    visual_baseline_dir: Path | None,
) -> None:
    if profile not in READINESS_CI_PROFILES:
        raise ValueError(f"unsupported scene readiness CI profile: {profile}")
    if not manifest_path.is_file():
        raise FileNotFoundError(f"scene readiness manifest not found: {manifest_path}")
    if not visual_policy_path.is_file():
        raise FileNotFoundError(f"visual baseline policy not found: {visual_policy_path}")
    if style_policy_path is not None and not style_policy_path.is_file():
        raise FileNotFoundError(f"scene style policy not found: {style_policy_path}")
    if adapter_policy_path is not None and not adapter_policy_path.is_file():
        raise FileNotFoundError(f"scene adapter policy not found: {adapter_policy_path}")
    if _profile_requires_baseline_dir(profile) and visual_baseline_dir is None:
        raise ValueError(f"{profile} requires --visual-baseline-dir")


def _profile_requires_baseline_dir(profile: ReadinessProfile) -> bool:
    return profile in {"visual-diff-local", "visual-diff-pinned", "baseline-refresh"}


def _normalize_for_stable_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_for_stable_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize_for_stable_json(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        normalized = round(value, 6)
        if normalized == 0:
            return 0
        if float(normalized).is_integer():
            return int(normalized)
        return normalized
    return value


if __name__ == "__main__":
    raise SystemExit(main())
