"""Opt-in SceneDeck readiness gate for curated scene-path fixtures."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..compat.state_io import load_state_file
from ..pipeline.pptx_object_validation import (
    PptxObjectValidationReport,
    ValidationMode,
    ValidationProfile,
    summarize_pptx_object_validation,
    validate_pptx_objects,
    validation_report_structural_hash,
    write_pptx_object_validation_report,
)
from ..pptx_compiler import adapt_blueprint_to_slide_ir
from ..pptx_scene_compiler import (
    ScenePptxCompileOutputs,
    ScenePptxCompileReport,
    compile_pptx_from_scene_deck,
    scene_pptx_compile_report_structural_hash,
    write_scene_pptx_compile_report,
)
from ..pipeline.pptx_screenshot_export import (
    ScreenshotExportImplementation,
    ScreenshotExporterDetection,
    ScreenshotExporterName,
    ScreenshotExportMode,
    ScreenshotExportReport,
    ScreenshotOutputFormat,
    export_pptx_screenshots,
    screenshot_export_report_structural_hash,
    write_screenshot_export_report,
)
from ..pipeline.scene_adapter_quality import (
    AdapterQualityFinding,
    AdapterQualityResult,
    AdapterQualitySummary,
    SceneAdapterPolicyFile,
    default_adapter_quality_policy,
    evaluate_adapter_quality_policy,
    load_scene_adapter_policy,
)
from ..pipeline.scene_style_quality import (
    SceneStylePolicyFile,
    StyleQualityFinding,
    StyleQualityResult,
    StyleQualitySummary,
    default_style_quality_policy,
    evaluate_style_quality_policy,
    load_scene_style_policy,
)
from ..pipeline.visual_regression import (
    VisualComparisonStatus,
    VisualRegressionMode,
    VisualRegressionReport,
    VisualThresholdPreset,
    build_visual_baseline_metadata,
    compare_screenshots_to_baseline,
    update_visual_baselines,
    visual_regression_report_structural_hash,
    visual_threshold_policy_from_preset,
    write_visual_regression_report,
)
from ..slide_scene import SceneDeck, scene_deck_structural_hash, scene_deck_to_stable_json
from ..slide_scene_adapter import adapt_slide_ir_document_to_scene_deck, scene_deck_adapter_summary


SCENE_READINESS_MANIFEST_SCHEMA = "scene_readiness_manifest"
SCENE_READINESS_MANIFEST_VERSION = "0.1"
SCENE_READINESS_REPORT_VERSION = "0.5"
FixtureKind = Literal["state", "scene_deck"]
FixtureStatus = Literal["passed", "failed"]
GateModeResult = Literal["passed", "issues_reported", "failed"]
AggregateScreenshotStatus = Literal["disabled", "passed", "issues_reported", "failed", "unavailable"]
AggregateVisualStatus = Literal["disabled", "passed", "issues_reported", "failed", "skipped"]
ReadinessProfile = Literal[
    "structural",
    "style-strict",
    "adapter-strict",
    "curated-strict",
    "visual-smoke",
    "visual-diff-local",
    "visual-diff-pinned",
    "baseline-refresh",
]
SceneGateProfile = ValidationProfile | ReadinessProfile
VISUAL_BASELINE_POLICY_SCHEMA = "visual_baseline_policy"
VISUAL_BASELINE_POLICY_VERSION = "0.1"


class SceneReadinessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SceneReadinessExpectedCounts(SceneReadinessModel):
    text: int = 0
    images: int = 0
    tables: int = 0
    charts: int = 0
    shapes: int = 0
    callouts: int = 0
    motifs: int = 0


class SceneReadinessFixtureSpec(SceneReadinessModel):
    fixture_id: str
    description: str
    fixture_kind: FixtureKind = "state"
    root_path: str | None = None
    blueprint_path: str | None = None
    design_system_path: str | None = Field(default=None, alias="design-system_path")
    deck_constitution_path: str | None = Field(default=None, alias="deck-constitution_path")
    layout_library_path: str | None = Field(default=None, alias="layout-library_path")
    slide_ledger_path: str | None = Field(default=None, alias="slide-ledger_path")
    asset_manifest_path: str | None = Field(default=None, alias="asset-manifest_path")
    viz_manifest_path: str | None = Field(default=None, alias="viz-manifest_path")
    scene_deck_path: str | None = None
    expected_slide_count: int
    expected_min_counts: SceneReadinessExpectedCounts = Field(default_factory=SceneReadinessExpectedCounts)
    expect_scene_strict_pass: bool = True

    @model_validator(mode="after")
    def _validate_fixture_shape(self) -> "SceneReadinessFixtureSpec":
        if self.expected_slide_count < 1:
            raise ValueError("expected_slide_count must be positive")
        if self.fixture_kind == "state":
            required = {
                "root_path": self.root_path,
                "blueprint_path": self.blueprint_path,
                "design_system_path": self.design_system_path,
                "deck_constitution_path": self.deck_constitution_path,
                "layout_library_path": self.layout_library_path,
                "slide_ledger_path": self.slide_ledger_path,
                "asset_manifest_path": self.asset_manifest_path,
                "viz_manifest_path": self.viz_manifest_path,
            }
            missing = sorted(key for key, value in required.items() if not value)
            if missing:
                raise ValueError(f"state fixture is missing required paths: {', '.join(missing)}")
        elif self.fixture_kind == "scene_deck" and not self.scene_deck_path:
            raise ValueError("scene_deck fixture requires scene_deck_path")
        return self


class SceneReadinessManifest(SceneReadinessModel):
    schema_name: Literal["scene_readiness_manifest"] = SCENE_READINESS_MANIFEST_SCHEMA
    schema_version: str = SCENE_READINESS_MANIFEST_VERSION
    fixtures: list[SceneReadinessFixtureSpec] = Field(default_factory=list)


class VisualBaselinePolicyProfile(SceneReadinessModel):
    profile_name: ReadinessProfile
    description: str
    fixture_ids: list[str] = Field(default_factory=list)
    baseline_dir: str | None = None
    threshold_preset: VisualThresholdPreset = "default"
    require_visual_baselines: bool = False
    screenshot_exporter: ScreenshotExporterName = "auto"
    screenshot_mode: ScreenshotExportMode = "inspect"
    visual_mode: VisualRegressionMode = "inspect"
    update_baselines_allowed: bool = False
    missing_baseline_behavior: Literal["warning", "enforceable"] = "warning"
    pinned_environment_required: bool = False
    allowed_environment_metadata_keys: list[str] = Field(default_factory=list)


class VisualBaselinePolicy(SceneReadinessModel):
    schema_name: Literal["visual_baseline_policy"] = VISUAL_BASELINE_POLICY_SCHEMA
    schema_version: str = VISUAL_BASELINE_POLICY_VERSION
    baseline_storage: Literal["external", "checked-in", "mixed"] = "external"
    checked_in_baselines_allowed: bool = False
    default_baseline_dir: str | None = None
    profiles: list[VisualBaselinePolicyProfile] = Field(default_factory=list)

    def profile_by_name(self, profile_name: ReadinessProfile) -> VisualBaselinePolicyProfile | None:
        for profile in self.profiles:
            if profile.profile_name == profile_name:
                return profile
        return None


class SceneReadinessActualCounts(SceneReadinessModel):
    text: int = 0
    images: int = 0
    tables: int = 0
    charts: int = 0
    shapes: int = 0
    callouts: int = 0
    motifs: int = 0


class SceneReadinessCheck(SceneReadinessModel):
    code: str
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)


class SceneReadinessArtifactPaths(SceneReadinessModel):
    fixture_dir: str
    scene_deck_path: str | None = None
    deck_pptx_path: str | None = None
    scene_compile_report_path: str | None = None
    pptx_object_report_path: str | None = None
    screenshots_dir: str | None = None
    screenshot_export_report_path: str | None = None
    visual_baseline_dir: str | None = None
    visual_diffs_dir: str | None = None
    visual_regression_report_path: str | None = None


class SceneReadinessFixtureResult(SceneReadinessModel):
    fixture_id: str
    description: str
    fixture_kind: FixtureKind
    status: FixtureStatus
    expect_scene_strict_pass: bool
    expected_slide_count: int
    actual_slide_count: int | None = None
    expected_min_counts: SceneReadinessExpectedCounts = Field(default_factory=SceneReadinessExpectedCounts)
    actual_counts: SceneReadinessActualCounts = Field(default_factory=SceneReadinessActualCounts)
    adapter_warning_count: int = 0
    adapter_warning_code_counts: dict[str, int] = Field(default_factory=dict)
    adapter_policy_profile: str | None = None
    adapter_policy_status: str = "disabled"
    adapter_policy_findings: list[AdapterQualityFinding] = Field(default_factory=list)
    adapter_policy_enforceable_count: int = 0
    adapter_policy_warning_count: int = 0
    adapter_quality_passed: bool = True
    adapter_quality_summary: AdapterQualitySummary = Field(default_factory=AdapterQualitySummary)
    compile_warning_count: int = 0
    compile_warning_code_counts: dict[str, int] = Field(default_factory=dict)
    style_warning_count: int = 0
    unresolved_theme_token_count: int = 0
    unresolved_font_token_count: int = 0
    unresolved_spacing_token_count: int = 0
    fallback_style_count: int = 0
    style_alias_count: int = 0
    deprecated_style_alias_count: int = 0
    ambiguous_style_alias_count: int = 0
    style_policy_profile: str | None = None
    style_policy_status: str = "disabled"
    style_policy_findings: list[StyleQualityFinding] = Field(default_factory=list)
    style_policy_enforceable_count: int = 0
    style_policy_warning_count: int = 0
    style_quality_passed: bool = True
    style_quality_summary: StyleQualitySummary = Field(default_factory=StyleQualitySummary)
    validator_finding_count: int = 0
    text_overflow_risk_count: int = 0
    trace_missing_count: int = 0
    duplicate_trace_count: int = 0
    scene_deck_structural_hash: str | None = None
    scene_compile_report_structural_hash: str | None = None
    validator_report_structural_hash: str | None = None
    validator_mode_result: str | None = None
    validator_profile: ValidationProfile | None = None
    object_validation_status: str = "disabled"
    combined_nonvisual_status: str = "disabled"
    combined_nonvisual_findings: int = 0
    combined_nonvisual_enforceable_count: int = 0
    curated_strict_passed: bool = True
    screenshot_export_status: str | None = None
    screenshot_exporter: str | None = None
    screenshot_exporter_available: bool | None = None
    screenshots_exported: int = 0
    screenshot_finding_count: int = 0
    screenshot_warning_count: int = 0
    screenshot_error_count: int = 0
    screenshot_report_structural_hash: str | None = None
    visual_comparison_status: VisualComparisonStatus | None = None
    visual_slides_compared: int = 0
    visual_finding_count: int = 0
    visual_warning_count: int = 0
    visual_error_count: int = 0
    visual_threshold_failure_count: int = 0
    visual_missing_baseline_count: int = 0
    baseline_refresh_count: int = 0
    visual_report_structural_hash: str | None = None
    checks: list[SceneReadinessCheck] = Field(default_factory=list)
    artifacts: SceneReadinessArtifactPaths
    execution_error: str | None = None


class SceneReadinessReport(SceneReadinessModel):
    report_version: str = SCENE_READINESS_REPORT_VERSION
    manifest_path: str
    mode: ValidationMode
    profile: ValidationProfile
    readiness_profile: ReadinessProfile | None = None
    visual_policy_path: str | None = None
    style_policy_path: str | None = None
    style_policy_profile: str | None = None
    style_policy_enabled: bool = False
    style_policy_status: str = "disabled"
    adapter_policy_path: str | None = None
    adapter_policy_profile: str | None = None
    adapter_policy_enabled: bool = False
    adapter_policy_status: str = "disabled"
    object_validation_status: str = "disabled"
    combined_nonvisual_status: str = "disabled"
    combined_nonvisual_findings: int = 0
    combined_nonvisual_enforceable_count: int = 0
    curated_strict_passed: bool = True
    pinned_environment_required: bool = False
    screenshots_enabled: bool = False
    screenshot_mode: ScreenshotExportMode | None = None
    screenshot_requested_exporter: ScreenshotExporterName | None = None
    screenshot_export_status: AggregateScreenshotStatus = "disabled"
    visual_diff_enabled: bool = False
    visual_mode: VisualRegressionMode | None = None
    visual_comparison_status: AggregateVisualStatus = "disabled"
    visual_threshold: str | None = None
    require_visual_baselines: bool = False
    write_diff_images: bool = False
    update_visual_baselines: bool = False
    baseline_refresh_count: int = 0
    mode_result: GateModeResult
    structural_hash: str
    fixture_count: int
    passed_fixture_count: int
    failed_fixture_count: int
    adapter_warning_count: int
    adapter_policy_finding_count: int = 0
    adapter_policy_enforceable_count: int = 0
    adapter_policy_warning_count: int = 0
    adapter_quality_passed: bool = True
    adapter_quality_summary: AdapterQualitySummary = Field(default_factory=AdapterQualitySummary)
    compile_warning_count: int
    style_warning_count: int = 0
    unresolved_theme_token_count: int = 0
    unresolved_font_token_count: int = 0
    unresolved_spacing_token_count: int = 0
    fallback_style_count: int = 0
    style_alias_count: int = 0
    deprecated_style_alias_count: int = 0
    ambiguous_style_alias_count: int = 0
    style_policy_finding_count: int = 0
    style_policy_enforceable_count: int = 0
    style_policy_warning_count: int = 0
    style_quality_passed: bool = True
    style_quality_summary: StyleQualitySummary = Field(default_factory=StyleQualitySummary)
    validator_finding_count: int
    text_overflow_risk_count: int
    trace_missing_count: int
    duplicate_trace_count: int
    screenshots_exported: int = 0
    screenshot_finding_count: int = 0
    screenshot_warning_count: int = 0
    screenshot_error_count: int = 0
    visual_slides_compared: int = 0
    visual_finding_count: int = 0
    visual_warning_count: int = 0
    visual_error_count: int = 0
    visual_threshold_failure_count: int = 0
    visual_missing_baseline_count: int = 0
    fixtures: list[SceneReadinessFixtureResult] = Field(default_factory=list)

    def to_stable_payload(self, *, include_paths: bool = True) -> dict[str, Any]:
        return scene_readiness_report_to_stable_payload(self, include_paths=include_paths)

    def to_stable_json(self) -> str:
        return scene_readiness_report_to_stable_json(self)


def load_scene_readiness_manifest(manifest_path: str | Path) -> SceneReadinessManifest:
    return SceneReadinessManifest.model_validate_json(Path(manifest_path).read_text(encoding="utf-8"))


def load_visual_baseline_policy(policy_path: str | Path) -> VisualBaselinePolicy:
    return VisualBaselinePolicy.model_validate_json(Path(policy_path).read_text(encoding="utf-8"))


def run_scene_readiness_gate_from_file(
    manifest_path: str | Path,
    *,
    output_dir: str | Path,
    fixture_ids: list[str] | None = None,
    mode: ValidationMode = "inspect",
    profile: SceneGateProfile = "scene-strict",
    screenshots: bool = False,
    screenshot_mode: ScreenshotExportMode = "inspect",
    screenshot_exporter: ScreenshotExporterName = "auto",
    screenshot_output_format: ScreenshotOutputFormat = "png",
    screenshot_export_impl: ScreenshotExportImplementation | None = None,
    screenshot_detection_override: ScreenshotExporterDetection | None = None,
    visual_diff: bool = False,
    visual_baseline_dir: str | Path | None = None,
    update_visual_baselines_flag: bool = False,
    visual_mode: VisualRegressionMode = "inspect",
    visual_threshold: VisualThresholdPreset = "default",
    require_visual_baselines: bool = False,
    write_diff_images: bool = False,
    visual_policy_path: str | Path | None = None,
    style_policy_path: str | Path | None = None,
    style_profile: str | None = None,
    enforce_style_policy: bool = False,
    adapter_policy_path: str | Path | None = None,
    adapter_profile: str | None = None,
    enforce_adapter_policy: bool = False,
    pinned_environment_required: bool = False,
) -> SceneReadinessReport:
    manifest_file = Path(manifest_path).resolve()
    manifest = load_scene_readiness_manifest(manifest_file)
    visual_policy_file = Path(visual_policy_path).resolve() if visual_policy_path is not None else None
    visual_policy = load_visual_baseline_policy(visual_policy_file) if visual_policy_file is not None else None
    style_policy_file = Path(style_policy_path).resolve() if style_policy_path is not None else None
    style_policy = load_scene_style_policy(style_policy_file) if style_policy_file is not None else None
    adapter_policy_file = Path(adapter_policy_path).resolve() if adapter_policy_path is not None else None
    adapter_policy = load_scene_adapter_policy(adapter_policy_file) if adapter_policy_file is not None else None
    readiness_profile: ReadinessProfile | None = profile if _is_readiness_profile(profile) else None  # type: ignore[assignment]
    validation_profile: ValidationProfile = "scene-strict" if readiness_profile else profile  # type: ignore[assignment]
    if readiness_profile in {"style-strict", "curated-strict"}:
        enforce_style_policy = True
        style_profile = style_profile or "style-strict"
    if readiness_profile in {"adapter-strict", "curated-strict"}:
        enforce_adapter_policy = True
        adapter_profile = adapter_profile or "adapter-strict"
    policy_profile = visual_policy.profile_by_name(readiness_profile) if visual_policy is not None and readiness_profile else None
    (
        fixture_ids,
        mode,
        screenshots,
        screenshot_mode,
        screenshot_exporter,
        visual_diff,
        update_visual_baselines_flag,
        visual_mode,
        visual_threshold,
        require_visual_baselines,
        pinned_environment_required,
        visual_baseline_dir,
    ) = _apply_readiness_profile(
        readiness_profile=readiness_profile,
        policy_profile=policy_profile,
        manifest_dir=manifest_file.parent,
        fixture_ids=fixture_ids,
        mode=mode,
        screenshots=screenshots,
        screenshot_mode=screenshot_mode,
        screenshot_exporter=screenshot_exporter,
        visual_diff=visual_diff,
        update_visual_baselines_flag=update_visual_baselines_flag,
        visual_mode=visual_mode,
        visual_threshold=visual_threshold,
        require_visual_baselines=require_visual_baselines,
        pinned_environment_required=pinned_environment_required,
        visual_baseline_dir=visual_baseline_dir,
    )
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    screenshots_enabled = screenshots or visual_diff or update_visual_baselines_flag
    baseline_root = (
        Path(visual_baseline_dir).resolve()
        if visual_baseline_dir is not None
        else (manifest_file.parent / "visual_baselines").resolve()
    )

    fixture_specs = manifest.fixtures
    if fixture_ids:
        requested = set(fixture_ids)
        fixture_specs = [fixture for fixture in manifest.fixtures if fixture.fixture_id in requested]
        missing = sorted(requested - {fixture.fixture_id for fixture in fixture_specs})
        if missing:
            raise KeyError(f"unknown scene readiness fixture ids: {', '.join(missing)}")

    fixture_results: list[SceneReadinessFixtureResult] = []
    for fixture in fixture_specs:
        fixture_results.append(
            _run_scene_readiness_fixture(
                fixture,
                manifest_path=manifest_file,
                output_root=output_root,
                mode=mode,
                profile=validation_profile,
                screenshots=screenshots_enabled,
                screenshot_mode=screenshot_mode,
                screenshot_exporter=screenshot_exporter,
                screenshot_output_format=screenshot_output_format,
                screenshot_export_impl=screenshot_export_impl,
                screenshot_detection_override=screenshot_detection_override,
                visual_diff=visual_diff,
                visual_baseline_root=baseline_root,
                update_visual_baselines_flag=update_visual_baselines_flag,
                visual_mode=visual_mode,
                visual_threshold=visual_threshold,
                require_visual_baselines=require_visual_baselines,
                write_diff_images=write_diff_images,
                readiness_profile=readiness_profile,
                style_policy=style_policy,
                style_profile=style_profile,
                enforce_style_policy=enforce_style_policy,
                adapter_policy=adapter_policy,
                adapter_profile=adapter_profile,
                enforce_adapter_policy=enforce_adapter_policy,
                pinned_environment_required=pinned_environment_required,
            )
        )

    passed_fixture_count = sum(1 for fixture in fixture_results if fixture.status == "passed")
    failed_fixture_count = len(fixture_results) - passed_fixture_count
    report = SceneReadinessReport(
        manifest_path=str(manifest_file),
        mode=mode,
        profile=validation_profile,
        readiness_profile=readiness_profile,
        visual_policy_path=str(visual_policy_file) if visual_policy_file is not None else None,
        style_policy_path=str(style_policy_file) if style_policy_file is not None else None,
        style_policy_profile=style_profile if enforce_style_policy else None,
        style_policy_enabled=enforce_style_policy,
        style_policy_status=_aggregate_style_policy_status(fixture_results, enabled=enforce_style_policy),
        adapter_policy_path=str(adapter_policy_file) if adapter_policy_file is not None else None,
        adapter_policy_profile=adapter_profile if enforce_adapter_policy else None,
        adapter_policy_enabled=enforce_adapter_policy,
        adapter_policy_status=_aggregate_adapter_policy_status(fixture_results, enabled=enforce_adapter_policy),
        object_validation_status=_aggregate_object_validation_status(fixture_results),
        combined_nonvisual_status=_aggregate_combined_nonvisual_status(
            fixture_results,
            enabled=readiness_profile == "curated-strict",
        ),
        combined_nonvisual_findings=sum(_fixture_combined_nonvisual_findings(fixture) for fixture in fixture_results),
        combined_nonvisual_enforceable_count=sum(_fixture_combined_nonvisual_enforceable_count(fixture) for fixture in fixture_results),
        curated_strict_passed=readiness_profile != "curated-strict" or all(fixture.curated_strict_passed for fixture in fixture_results),
        pinned_environment_required=pinned_environment_required,
        screenshots_enabled=screenshots_enabled,
        screenshot_mode=screenshot_mode if screenshots_enabled else None,
        screenshot_requested_exporter=screenshot_exporter if screenshots_enabled else None,
        screenshot_export_status=_aggregate_screenshot_status(fixture_results, screenshots_enabled=screenshots_enabled),
        visual_diff_enabled=visual_diff,
        visual_mode=visual_mode if visual_diff else None,
        visual_comparison_status=_aggregate_visual_status(fixture_results, visual_diff_enabled=visual_diff),
        visual_threshold=visual_threshold if visual_diff else None,
        require_visual_baselines=require_visual_baselines if visual_diff else False,
        write_diff_images=write_diff_images if visual_diff else False,
        update_visual_baselines=update_visual_baselines_flag,
        baseline_refresh_count=sum(fixture.baseline_refresh_count for fixture in fixture_results),
        mode_result=_scene_readiness_mode_result(
            mode,
            screenshot_mode,
            visual_mode,
            failed_fixture_count,
            screenshots_enabled=screenshots_enabled,
            visual_diff_enabled=visual_diff,
        ),
        structural_hash="",
        fixture_count=len(fixture_results),
        passed_fixture_count=passed_fixture_count,
        failed_fixture_count=failed_fixture_count,
        adapter_warning_count=sum(fixture.adapter_warning_count for fixture in fixture_results),
        adapter_policy_finding_count=sum(len(fixture.adapter_policy_findings) for fixture in fixture_results),
        adapter_policy_enforceable_count=sum(fixture.adapter_policy_enforceable_count for fixture in fixture_results),
        adapter_policy_warning_count=sum(fixture.adapter_policy_warning_count for fixture in fixture_results),
        adapter_quality_passed=all(fixture.adapter_quality_passed for fixture in fixture_results),
        adapter_quality_summary=_aggregate_adapter_quality_summary(fixture_results),
        compile_warning_count=sum(fixture.compile_warning_count for fixture in fixture_results),
        style_warning_count=sum(fixture.style_warning_count for fixture in fixture_results),
        unresolved_theme_token_count=sum(fixture.unresolved_theme_token_count for fixture in fixture_results),
        unresolved_font_token_count=sum(fixture.unresolved_font_token_count for fixture in fixture_results),
        unresolved_spacing_token_count=sum(fixture.unresolved_spacing_token_count for fixture in fixture_results),
        fallback_style_count=sum(fixture.fallback_style_count for fixture in fixture_results),
        style_alias_count=sum(fixture.style_alias_count for fixture in fixture_results),
        deprecated_style_alias_count=sum(fixture.deprecated_style_alias_count for fixture in fixture_results),
        ambiguous_style_alias_count=sum(fixture.ambiguous_style_alias_count for fixture in fixture_results),
        style_policy_finding_count=sum(len(fixture.style_policy_findings) for fixture in fixture_results),
        style_policy_enforceable_count=sum(fixture.style_policy_enforceable_count for fixture in fixture_results),
        style_policy_warning_count=sum(fixture.style_policy_warning_count for fixture in fixture_results),
        style_quality_passed=all(fixture.style_quality_passed for fixture in fixture_results),
        style_quality_summary=_aggregate_style_quality_summary(fixture_results),
        validator_finding_count=sum(fixture.validator_finding_count for fixture in fixture_results),
        text_overflow_risk_count=sum(fixture.text_overflow_risk_count for fixture in fixture_results),
        trace_missing_count=sum(fixture.trace_missing_count for fixture in fixture_results),
        duplicate_trace_count=sum(fixture.duplicate_trace_count for fixture in fixture_results),
        screenshots_exported=sum(fixture.screenshots_exported for fixture in fixture_results),
        screenshot_finding_count=sum(fixture.screenshot_finding_count for fixture in fixture_results),
        screenshot_warning_count=sum(fixture.screenshot_warning_count for fixture in fixture_results),
        screenshot_error_count=sum(fixture.screenshot_error_count for fixture in fixture_results),
        visual_slides_compared=sum(fixture.visual_slides_compared for fixture in fixture_results),
        visual_finding_count=sum(fixture.visual_finding_count for fixture in fixture_results),
        visual_warning_count=sum(fixture.visual_warning_count for fixture in fixture_results),
        visual_error_count=sum(fixture.visual_error_count for fixture in fixture_results),
        visual_threshold_failure_count=sum(fixture.visual_threshold_failure_count for fixture in fixture_results),
        visual_missing_baseline_count=sum(fixture.visual_missing_baseline_count for fixture in fixture_results),
        fixtures=fixture_results,
    )
    return report.model_copy(update={"structural_hash": scene_readiness_report_structural_hash(report)})


def write_scene_readiness_report(report: SceneReadinessReport, output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(scene_readiness_report_to_stable_json(report) + "\n", encoding="utf-8")
    return destination


def summarize_scene_readiness_report(report: SceneReadinessReport) -> list[str]:
    header = (
        "SCENE_READINESS_GATE "
        f"fixtures={report.fixture_count} "
        f"passed={report.passed_fixture_count} "
        f"failed={report.failed_fixture_count} "
        f"warnings={report.adapter_warning_count + report.compile_warning_count} "
        f"object_status={report.object_validation_status} "
        f"combined_nonvisual_status={report.combined_nonvisual_status} "
        f"combined_nonvisual_enforceable={report.combined_nonvisual_enforceable_count} "
        f"adapter_status={report.adapter_policy_status} "
        f"adapter_findings={report.adapter_policy_finding_count} "
        f"adapter_enforceable={report.adapter_policy_enforceable_count} "
        f"style_warnings={report.style_warning_count} "
        f"style_aliases={report.style_alias_count} "
        f"style_status={report.style_policy_status} "
        f"style_findings={report.style_policy_finding_count} "
        f"style_enforceable={report.style_policy_enforceable_count} "
        f"findings={report.validator_finding_count} "
        f"text_overflow_risk={report.text_overflow_risk_count} "
        f"trace_missing={report.trace_missing_count} "
        f"duplicate_traces={report.duplicate_trace_count}"
    )
    if report.screenshots_enabled:
        header += (
            f" screenshots={report.screenshots_exported} "
            f"screenshot_status={report.screenshot_export_status} "
            f"screenshot_findings={report.screenshot_finding_count} "
            f"screenshot_warnings={report.screenshot_warning_count} "
            f"screenshot_errors={report.screenshot_error_count}"
        )
    if report.visual_diff_enabled:
        header += (
            f" visual_status={report.visual_comparison_status} "
            f"visual_compared={report.visual_slides_compared} "
            f"visual_findings={report.visual_finding_count} "
            f"visual_threshold_failures={report.visual_threshold_failure_count} "
            f"visual_missing_baselines={report.visual_missing_baseline_count}"
        )
    if report.update_visual_baselines:
        header += f" baselines_updated={report.baseline_refresh_count}"
    lines = [header]
    for fixture in report.fixtures:
        line = (
            "FIXTURE "
            f"id={fixture.fixture_id} "
            f"status={fixture.status} "
            f"slides={fixture.actual_slide_count if fixture.actual_slide_count is not None else 'n/a'} "
            f"warnings={fixture.adapter_warning_count + fixture.compile_warning_count} "
            f"object_status={fixture.object_validation_status} "
            f"combined_nonvisual_status={fixture.combined_nonvisual_status} "
            f"adapter_status={fixture.adapter_policy_status} "
            f"adapter_findings={len(fixture.adapter_policy_findings)} "
            f"style_warnings={fixture.style_warning_count} "
            f"style_aliases={fixture.style_alias_count} "
            f"style_status={fixture.style_policy_status} "
            f"style_findings={len(fixture.style_policy_findings)} "
            f"findings={fixture.validator_finding_count}"
        )
        if report.screenshots_enabled:
            line += (
                f" screenshots={fixture.screenshots_exported} "
                f"screenshot_status={fixture.screenshot_export_status or 'disabled'}"
            )
        if report.visual_diff_enabled:
            line += (
                f" visual_status={fixture.visual_comparison_status or 'disabled'} "
                f"visual_compared={fixture.visual_slides_compared}"
            )
        lines.append(line)
    return lines


def scene_readiness_report_to_stable_payload(
    report: SceneReadinessReport,
    *,
    include_paths: bool = True,
) -> dict[str, Any]:
    payload = report.model_dump(mode="json", exclude_none=True, by_alias=True)
    if not include_paths:
        payload.pop("manifest_path", None)
        payload.pop("visual_policy_path", None)
        payload.pop("structural_hash", None)
    return _normalize_for_stable_json(payload)


def scene_readiness_report_to_stable_json(report: SceneReadinessReport) -> str:
    return json.dumps(scene_readiness_report_to_stable_payload(report), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def scene_readiness_report_structural_hash(report: SceneReadinessReport) -> str:
    payload = scene_readiness_report_to_stable_payload(report, include_paths=False)
    payload.pop("structural_hash", None)
    stable_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


def _run_scene_readiness_fixture(
    fixture: SceneReadinessFixtureSpec,
    *,
    manifest_path: Path,
    output_root: Path,
    mode: ValidationMode,
    profile: ValidationProfile,
    screenshots: bool,
    screenshot_mode: ScreenshotExportMode,
    screenshot_exporter: ScreenshotExporterName,
    screenshot_output_format: ScreenshotOutputFormat,
    screenshot_export_impl: ScreenshotExportImplementation | None,
    screenshot_detection_override: ScreenshotExporterDetection | None,
    visual_diff: bool,
    visual_baseline_root: Path,
    update_visual_baselines_flag: bool,
    visual_mode: VisualRegressionMode,
    visual_threshold: VisualThresholdPreset,
    require_visual_baselines: bool,
    write_diff_images: bool,
    readiness_profile: ReadinessProfile | None,
    style_policy: SceneStylePolicyFile | None,
    style_profile: str | None,
    enforce_style_policy: bool,
    adapter_policy: SceneAdapterPolicyFile | None,
    adapter_profile: str | None,
    enforce_adapter_policy: bool,
    pinned_environment_required: bool,
) -> SceneReadinessFixtureResult:
    fixture_dir = output_root / "fixtures" / fixture.fixture_id
    fixture_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths = SceneReadinessArtifactPaths(
        fixture_dir=_relative_artifact_path(fixture_dir, output_root),
        scene_deck_path=_relative_artifact_path(fixture_dir / "scene-deck.json", output_root),
        deck_pptx_path=_relative_artifact_path(fixture_dir / "deck.pptx", output_root),
        scene_compile_report_path=_relative_artifact_path(fixture_dir / "scene-compile-report.json", output_root),
        pptx_object_report_path=_relative_artifact_path(fixture_dir / "pptx-object-report.json", output_root),
        screenshots_dir=_relative_artifact_path(fixture_dir / "screenshots", output_root) if screenshots else None,
        screenshot_export_report_path=_relative_artifact_path(fixture_dir / "screenshot-export-report.json", output_root) if screenshots else None,
        visual_baseline_dir=_relative_artifact_path(visual_baseline_root / fixture.fixture_id, output_root)
        if visual_diff and _is_relative_to(visual_baseline_root / fixture.fixture_id, output_root)
        else (str((visual_baseline_root / fixture.fixture_id).resolve()) if visual_diff else None),
        visual_diffs_dir=_relative_artifact_path(fixture_dir / "visual-diffs", output_root) if visual_diff and write_diff_images else None,
        visual_regression_report_path=_relative_artifact_path(fixture_dir / "visual-regression-report.json", output_root) if visual_diff else None,
    )
    try:
        scene_deck, root_path = _load_or_adapt_scene_deck(fixture, manifest_path)
        scene_deck_path = fixture_dir / "scene-deck.json"
        scene_deck_path.write_text(scene_deck_to_stable_json(scene_deck) + "\n", encoding="utf-8")
        adapter_summary = scene_deck_adapter_summary(scene_deck)
        adapter_warning_counts = dict(sorted(adapter_summary["warning_code_counts"].items()))
        fixture_adapter_profile, fixture_adapter_policy = _adapter_policy_for_fixture(
            adapter_policy,
            fixture_id=fixture.fixture_id,
            adapter_profile=adapter_profile,
            enabled=enforce_adapter_policy,
        )
        adapter_quality_result = evaluate_adapter_quality_policy(
            adapter_summary,
            policy=fixture_adapter_policy,
            profile=fixture_adapter_profile,
            fixture_id=fixture.fixture_id,
        )
        compile_outputs = compile_pptx_from_scene_deck(
            scene_deck,
            fixture_dir,
            root=root_path,
            scene_deck_path=scene_deck_path,
        )
        fixture_style_profile, fixture_style_policy = _style_policy_for_fixture(
            style_policy,
            fixture_id=fixture.fixture_id,
            style_profile=style_profile,
            enabled=enforce_style_policy,
        )
        style_quality_result = evaluate_style_quality_policy(
            compile_outputs.report,
            policy=fixture_style_policy,
            profile=fixture_style_profile,
            fixture_id=fixture.fixture_id,
            deck_id=scene_deck.deck_id,
        )
        compile_report_path = write_scene_pptx_compile_report(compile_outputs.report, fixture_dir / "scene-compile-report.json")
        validation_report = validate_pptx_objects(
            compile_outputs.pptx_path,
            scene_deck=scene_deck,
            scene_deck_path=scene_deck_path,
            mode=mode,
            profile=profile,
        )
        validation_report_path = write_pptx_object_validation_report(validation_report, fixture_dir / "pptx-object-report.json")
        screenshot_report: ScreenshotExportReport | None = None
        screenshot_report_path: Path | None = None
        if screenshots:
            screenshot_report = export_pptx_screenshots(
                compile_outputs.pptx_path,
                output_dir=fixture_dir / "screenshots",
                slide_count_expected=compile_outputs.report.slide_count,
                mode=screenshot_mode,
                exporter=screenshot_exporter,
                output_format=screenshot_output_format,
                export_impl=screenshot_export_impl,
                detection_override=screenshot_detection_override,
            )
            screenshot_report_path = write_screenshot_export_report(
                screenshot_report,
                fixture_dir / "screenshot-export-report.json",
            )
        visual_report: VisualRegressionReport | None = None
        visual_report_path: Path | None = None
        baseline_refresh_count = 0
        baseline_fixture_dir = visual_baseline_root / fixture.fixture_id
        if update_visual_baselines_flag and screenshot_report is not None:
            updated_baselines = update_visual_baselines(
                screenshot_dir=fixture_dir / "screenshots",
                baseline_dir=baseline_fixture_dir,
                slide_count_expected=compile_outputs.report.slide_count,
                metadata=build_visual_baseline_metadata(
                    fixture_id=fixture.fixture_id,
                    screenshot_dir=fixture_dir / "screenshots",
                    slide_count=compile_outputs.report.slide_count,
                    profile_name=readiness_profile,
                    screenshot_exporter=screenshot_report.exporter,
                ),
            )
            baseline_refresh_count = len(updated_baselines)
        if visual_diff and screenshot_report is not None:
            visual_report = compare_screenshots_to_baseline(
                fixture_id=fixture.fixture_id,
                screenshot_dir=fixture_dir / "screenshots",
                baseline_dir=baseline_fixture_dir,
                output_dir=fixture_dir,
                slide_count_expected=compile_outputs.report.slide_count,
                mode=visual_mode,
                threshold_policy=visual_threshold_policy_from_preset(visual_threshold),
                require_visual_baselines=require_visual_baselines,
                write_diff_images=write_diff_images,
                pptx_path=compile_outputs.pptx_path,
                screenshot_report_path=screenshot_report_path,
                screenshot_exporter=screenshot_report.exporter,
                profile_name=readiness_profile,
                pinned_environment_required=pinned_environment_required,
                expected_screenshot_exporter=screenshot_exporter if pinned_environment_required else None,
            )
            visual_report_path = write_visual_regression_report(
                visual_report,
                fixture_dir / "visual-regression-report.json",
            )
        actual_counts = _actual_counts_from_compile_report(compile_outputs.report)
        checks = _fixture_checks(
            fixture,
            actual_slide_count=compile_outputs.report.slide_count,
            actual_counts=actual_counts,
            validation_report=validation_report,
            profile=profile,
            screenshot_report=screenshot_report,
            screenshot_mode=screenshot_mode,
            visual_report=visual_report,
            visual_mode=visual_mode,
            style_quality_result=style_quality_result,
            adapter_quality_result=adapter_quality_result,
            mode=mode,
        )
        status: FixtureStatus = "passed" if all(check.passed for check in checks) else "failed"
        compile_warning_counts = dict(sorted(Counter(warning.code for warning in compile_outputs.report.warnings).items()))
        return SceneReadinessFixtureResult(
            fixture_id=fixture.fixture_id,
            description=fixture.description,
            fixture_kind=fixture.fixture_kind,
            status=status,
            expect_scene_strict_pass=fixture.expect_scene_strict_pass,
            expected_slide_count=fixture.expected_slide_count,
            actual_slide_count=compile_outputs.report.slide_count,
            expected_min_counts=fixture.expected_min_counts,
            actual_counts=actual_counts,
            adapter_warning_count=sum(adapter_warning_counts.values()),
            adapter_warning_code_counts=adapter_warning_counts,
            adapter_policy_profile=adapter_quality_result.profile,
            adapter_policy_status=adapter_quality_result.status,
            adapter_policy_findings=adapter_quality_result.findings,
            adapter_policy_enforceable_count=adapter_quality_result.enforceable_count,
            adapter_policy_warning_count=adapter_quality_result.warning_count,
            adapter_quality_passed=adapter_quality_result.passed,
            adapter_quality_summary=adapter_quality_result.summary,
            compile_warning_count=len(compile_outputs.report.warnings),
            compile_warning_code_counts=compile_warning_counts,
            style_warning_count=compile_outputs.report.style_warning_count,
            unresolved_theme_token_count=compile_outputs.report.unresolved_theme_token_count,
            unresolved_font_token_count=compile_outputs.report.unresolved_font_token_count,
            unresolved_spacing_token_count=compile_outputs.report.unresolved_spacing_token_count,
            fallback_style_count=compile_outputs.report.fallback_style_count,
            style_alias_count=compile_outputs.report.style_alias_count,
            deprecated_style_alias_count=compile_outputs.report.deprecated_style_alias_count,
            ambiguous_style_alias_count=compile_outputs.report.ambiguous_style_alias_count,
            style_policy_profile=style_quality_result.profile,
            style_policy_status=style_quality_result.status,
            style_policy_findings=style_quality_result.findings,
            style_policy_enforceable_count=style_quality_result.enforceable_count,
            style_policy_warning_count=style_quality_result.warning_count,
            style_quality_passed=style_quality_result.passed,
            style_quality_summary=style_quality_result.summary,
            validator_finding_count=validation_report.findings_summary.total_findings,
            text_overflow_risk_count=validation_report.overflow_risk_count,
            trace_missing_count=validation_report.missing_trace_count,
            duplicate_trace_count=validation_report.duplicate_trace_count,
            scene_deck_structural_hash=scene_deck_structural_hash(scene_deck),
            scene_compile_report_structural_hash=scene_pptx_compile_report_structural_hash(compile_outputs.report),
            validator_report_structural_hash=validation_report_structural_hash(validation_report),
            validator_mode_result=validation_report.mode_result,
            validator_profile=validation_report.profile,
            object_validation_status=validation_report.mode_result,
            combined_nonvisual_status=_fixture_combined_nonvisual_status_from_parts(
                object_validation_status=validation_report.mode_result,
                style_policy_status=style_quality_result.status,
                adapter_policy_status=adapter_quality_result.status,
                enabled=readiness_profile == "curated-strict",
            ),
            combined_nonvisual_findings=(
                validation_report.findings_summary.total_findings
                + len(style_quality_result.findings)
                + len(adapter_quality_result.findings)
            ),
            combined_nonvisual_enforceable_count=(
                validation_report.findings_summary.total_findings
                + style_quality_result.enforceable_count
                + adapter_quality_result.enforceable_count
            ),
            curated_strict_passed=(
                readiness_profile != "curated-strict"
                or (
                    validation_report.mode_result == "passed"
                    and style_quality_result.status == "passed"
                    and adapter_quality_result.status == "passed"
                )
            ),
            screenshot_export_status=screenshot_report.export_status if screenshot_report is not None else None,
            screenshot_exporter=screenshot_report.exporter if screenshot_report is not None else None,
            screenshot_exporter_available=screenshot_report.exporter_available if screenshot_report is not None else None,
            screenshots_exported=screenshot_report.screenshots_exported if screenshot_report is not None else 0,
            screenshot_finding_count=screenshot_report.findings_summary.total_findings if screenshot_report is not None else 0,
            screenshot_warning_count=screenshot_report.findings_summary.warning_count if screenshot_report is not None else 0,
            screenshot_error_count=screenshot_report.findings_summary.error_count if screenshot_report is not None else 0,
            screenshot_report_structural_hash=(
                screenshot_export_report_structural_hash(screenshot_report) if screenshot_report is not None else None
            ),
            visual_comparison_status=visual_report.comparison_status if visual_report is not None else None,
            visual_slides_compared=visual_report.slide_count_compared if visual_report is not None else 0,
            visual_finding_count=visual_report.findings_summary.total_findings if visual_report is not None else 0,
            visual_warning_count=visual_report.findings_summary.warning_count if visual_report is not None else 0,
            visual_error_count=visual_report.findings_summary.error_count if visual_report is not None else 0,
            visual_threshold_failure_count=visual_report.threshold_failures if visual_report is not None else 0,
            visual_missing_baseline_count=visual_report.slide_count_missing_baseline if visual_report is not None else 0,
            baseline_refresh_count=baseline_refresh_count,
            visual_report_structural_hash=(
                visual_regression_report_structural_hash(visual_report) if visual_report is not None else None
            ),
            checks=checks,
            artifacts=artifact_paths.model_copy(
                update={
                    "scene_deck_path": _relative_artifact_path(scene_deck_path, output_root),
                    "deck_pptx_path": _relative_artifact_path(compile_outputs.pptx_path, output_root),
                    "scene_compile_report_path": _relative_artifact_path(compile_report_path, output_root),
                    "pptx_object_report_path": _relative_artifact_path(validation_report_path, output_root),
                    "screenshots_dir": (
                        _relative_artifact_path((fixture_dir / "screenshots").resolve(), output_root)
                        if screenshot_report is not None
                        else None
                    ),
                    "screenshot_export_report_path": (
                        _relative_artifact_path(screenshot_report_path, output_root)
                        if screenshot_report_path is not None
                        else None
                    ),
                    "visual_baseline_dir": (
                        _relative_artifact_path(baseline_fixture_dir, output_root)
                        if _is_relative_to(baseline_fixture_dir, output_root)
                        else (str(baseline_fixture_dir.resolve()) if visual_diff else None)
                    ),
                    "visual_diffs_dir": (
                        _relative_artifact_path(fixture_dir / "visual-diffs", output_root)
                        if visual_report is not None and write_diff_images
                        else None
                    ),
                    "visual_regression_report_path": (
                        _relative_artifact_path(visual_report_path, output_root)
                        if visual_report_path is not None
                        else None
                    ),
                }
            ),
        )
    except Exception as exc:
        return SceneReadinessFixtureResult(
            fixture_id=fixture.fixture_id,
            description=fixture.description,
            fixture_kind=fixture.fixture_kind,
            status="failed",
            expect_scene_strict_pass=fixture.expect_scene_strict_pass,
            expected_slide_count=fixture.expected_slide_count,
            expected_min_counts=fixture.expected_min_counts,
            object_validation_status="failed" if readiness_profile == "curated-strict" else "disabled",
            combined_nonvisual_status="failed" if readiness_profile == "curated-strict" else "disabled",
            combined_nonvisual_findings=1 if readiness_profile == "curated-strict" else 0,
            combined_nonvisual_enforceable_count=1 if readiness_profile == "curated-strict" else 0,
            curated_strict_passed=readiness_profile != "curated-strict",
            artifacts=artifact_paths,
            execution_error=str(exc),
            checks=[
                SceneReadinessCheck(
                    code="fixture_execution",
                    passed=False,
                    details={"error": str(exc)},
                )
            ],
        )


def _load_or_adapt_scene_deck(
    fixture: SceneReadinessFixtureSpec,
    manifest_path: Path,
) -> tuple[SceneDeck, Path | None]:
    manifest_dir = manifest_path.parent
    if fixture.fixture_kind == "scene_deck":
        scene_deck_path = _resolve_fixture_path(manifest_dir, fixture.root_path, fixture.scene_deck_path)
        scene_deck = SceneDeck.model_validate_json(scene_deck_path.read_text(encoding="utf-8"))
        root_path = _resolve_root_path(manifest_dir, fixture.root_path)
        return scene_deck, root_path or scene_deck_path.parent

    root_path = _resolve_root_path(manifest_dir, fixture.root_path)
    if root_path is None:
        raise ValueError("state fixture requires root_path")
    slide_ir = adapt_blueprint_to_slide_ir(
        blueprint=load_state_file(_resolve_fixture_path(manifest_dir, fixture.root_path, fixture.blueprint_path)),
        design_system=load_state_file(_resolve_fixture_path(manifest_dir, fixture.root_path, fixture.design_system_path)),
        deck_constitution=load_state_file(_resolve_fixture_path(manifest_dir, fixture.root_path, fixture.deck_constitution_path)),
        layout_library=load_state_file(_resolve_fixture_path(manifest_dir, fixture.root_path, fixture.layout_library_path)),
        slide_ledger=load_state_file(_resolve_fixture_path(manifest_dir, fixture.root_path, fixture.slide_ledger_path)),
        asset_manifest=load_state_file(_resolve_fixture_path(manifest_dir, fixture.root_path, fixture.asset_manifest_path)),
        viz_manifest=load_state_file(_resolve_fixture_path(manifest_dir, fixture.root_path, fixture.viz_manifest_path)),
    )
    return adapt_slide_ir_document_to_scene_deck(slide_ir), root_path


def _fixture_checks(
    fixture: SceneReadinessFixtureSpec,
    *,
    actual_slide_count: int,
    actual_counts: SceneReadinessActualCounts,
    validation_report: PptxObjectValidationReport,
    profile: ValidationProfile,
    screenshot_report: ScreenshotExportReport | None,
    screenshot_mode: ScreenshotExportMode,
    visual_report: VisualRegressionReport | None,
    visual_mode: VisualRegressionMode,
    style_quality_result: StyleQualityResult,
    adapter_quality_result: AdapterQualityResult,
    mode: ValidationMode,
) -> list[SceneReadinessCheck]:
    checks: list[SceneReadinessCheck] = []
    checks.append(
        SceneReadinessCheck(
            code="expected_slide_count",
            passed=actual_slide_count == fixture.expected_slide_count,
            details={"expected": fixture.expected_slide_count, "actual": actual_slide_count},
        )
    )
    minimum_failures: dict[str, dict[str, int]] = {}
    for field in SceneReadinessExpectedCounts.model_fields:
        expected_min = int(getattr(fixture.expected_min_counts, field))
        actual_value = int(getattr(actual_counts, field))
        if actual_value < expected_min:
            minimum_failures[field] = {"expected_min": expected_min, "actual": actual_value}
    checks.append(
        SceneReadinessCheck(
            code="expected_min_object_counts",
            passed=not minimum_failures,
            details={"mismatches": minimum_failures} if minimum_failures else {"status": "ok"},
        )
    )
    checks.append(
        SceneReadinessCheck(
            code="scene_strict_expected_result",
            passed=(validation_report.mode_result == "passed") == fixture.expect_scene_strict_pass,
            details={
                "expected_scene_strict_pass": fixture.expect_scene_strict_pass,
                "actual_mode_result": validation_report.mode_result,
            },
        )
    )
    checks.append(
        SceneReadinessCheck(
            code="validator_profile",
            passed=validation_report.profile == profile,
            details={"expected_profile": profile, "actual_profile": validation_report.profile},
        )
    )
    if screenshot_report is not None:
        checks.append(
            SceneReadinessCheck(
                code="screenshot_export_status",
                passed=(screenshot_mode != "enforce") or screenshot_report.export_status == "passed",
                details={
                    "screenshot_mode": screenshot_mode,
                    "export_status": screenshot_report.export_status,
                    "findings": screenshot_report.findings_summary.total_findings,
                    "warnings": screenshot_report.findings_summary.warning_count,
                    "errors": screenshot_report.findings_summary.error_count,
                },
            )
        )
    if visual_report is not None:
        checks.append(
            SceneReadinessCheck(
                code="visual_regression_status",
                passed=(visual_mode != "enforce") or visual_report.comparison_status == "passed",
                details={
                    "visual_mode": visual_mode,
                    "comparison_status": visual_report.comparison_status,
                    "findings": visual_report.findings_summary.total_findings,
                    "threshold_failures": visual_report.threshold_failures,
                    "missing_baselines": visual_report.slide_count_missing_baseline,
                },
            )
        )
    if style_quality_result.enabled:
        checks.append(
            SceneReadinessCheck(
                code="style_quality_policy",
                passed=(mode != "enforce") or style_quality_result.enforceable_count == 0,
                details={
                    "mode": mode,
                    "profile": style_quality_result.profile,
                    "status": style_quality_result.status,
                    "findings": len(style_quality_result.findings),
                    "enforceable": style_quality_result.enforceable_count,
                },
            )
        )
    if adapter_quality_result.enabled:
        checks.append(
            SceneReadinessCheck(
                code="adapter_quality_policy",
                passed=(mode != "enforce") or adapter_quality_result.enforceable_count == 0,
                details={
                    "mode": mode,
                    "profile": adapter_quality_result.profile,
                    "status": adapter_quality_result.status,
                    "findings": len(adapter_quality_result.findings),
                    "enforceable": adapter_quality_result.enforceable_count,
                },
            )
        )
    return checks


def _actual_counts_from_compile_report(report: ScenePptxCompileReport) -> SceneReadinessActualCounts:
    return SceneReadinessActualCounts(
        text=report.rendered_text_object_count,
        images=report.rendered_image_object_count,
        tables=report.rendered_native_table_count,
        charts=report.rendered_native_chart_count,
        shapes=report.rendered_shape_object_count,
        callouts=report.rendered_callout_object_count,
        motifs=report.rendered_background_motif_count,
    )


def _resolve_root_path(manifest_dir: Path, root_path: str | None) -> Path | None:
    if root_path is None:
        return None
    path = Path(root_path)
    if not path.is_absolute():
        path = (manifest_dir / path).resolve()
    return path


def _resolve_fixture_path(manifest_dir: Path, root_path: str | None, path_text: str | None) -> Path:
    if not path_text:
        raise ValueError("fixture path is required")
    path = Path(path_text)
    if path.is_absolute():
        return path
    root = _resolve_root_path(manifest_dir, root_path)
    if root is not None:
        return (root / path).resolve()
    return (manifest_dir / path).resolve()


def _relative_artifact_path(path: Path, output_root: Path) -> str:
    return path.resolve().relative_to(output_root.resolve()).as_posix()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _is_readiness_profile(profile: str) -> bool:
    return profile in {
        "structural",
        "style-strict",
        "adapter-strict",
        "curated-strict",
        "visual-smoke",
        "visual-diff-local",
        "visual-diff-pinned",
        "baseline-refresh",
    }


def _apply_readiness_profile(
    *,
    readiness_profile: ReadinessProfile | None,
    policy_profile: VisualBaselinePolicyProfile | None,
    manifest_dir: Path,
    fixture_ids: list[str] | None,
    mode: ValidationMode,
    screenshots: bool,
    screenshot_mode: ScreenshotExportMode,
    screenshot_exporter: ScreenshotExporterName,
    visual_diff: bool,
    update_visual_baselines_flag: bool,
    visual_mode: VisualRegressionMode,
    visual_threshold: VisualThresholdPreset,
    require_visual_baselines: bool,
    pinned_environment_required: bool,
    visual_baseline_dir: str | Path | None,
) -> tuple[
    list[str] | None,
    ValidationMode,
    bool,
    ScreenshotExportMode,
    ScreenshotExporterName,
    bool,
    bool,
    VisualRegressionMode,
    VisualThresholdPreset,
    bool,
    bool,
    str | Path | None,
]:
    if readiness_profile is None:
        return (
            fixture_ids,
            mode,
            screenshots,
            screenshot_mode,
            screenshot_exporter,
            visual_diff,
            update_visual_baselines_flag,
            visual_mode,
            visual_threshold,
            require_visual_baselines,
            pinned_environment_required,
            visual_baseline_dir,
        )
    if readiness_profile in {"structural", "style-strict", "adapter-strict", "curated-strict"}:
        mode = "enforce"
        screenshots = False
        visual_diff = False
    elif readiness_profile == "visual-smoke":
        mode = "enforce"
        screenshots = True
        screenshot_mode = "inspect"
        visual_diff = False
    elif readiness_profile == "visual-diff-local":
        mode = "enforce"
        screenshots = True
        screenshot_mode = "inspect"
        visual_diff = True
        visual_mode = "inspect"
        require_visual_baselines = False
    elif readiness_profile == "visual-diff-pinned":
        mode = "enforce"
        screenshots = True
        screenshot_mode = "enforce"
        screenshot_exporter = "powerpoint"
        visual_diff = True
        visual_mode = "enforce"
        require_visual_baselines = True
        pinned_environment_required = True
    elif readiness_profile == "baseline-refresh":
        mode = "enforce"
        screenshots = True
        screenshot_mode = "inspect"
        visual_diff = False
        update_visual_baselines_flag = True
    if policy_profile is not None:
        if fixture_ids is None and policy_profile.fixture_ids:
            fixture_ids = list(policy_profile.fixture_ids)
        screenshot_exporter = policy_profile.screenshot_exporter
        screenshot_mode = policy_profile.screenshot_mode
        visual_mode = policy_profile.visual_mode
        visual_threshold = policy_profile.threshold_preset
        require_visual_baselines = policy_profile.require_visual_baselines
        pinned_environment_required = policy_profile.pinned_environment_required
        if policy_profile.baseline_dir and visual_baseline_dir is None:
            baseline_path = Path(policy_profile.baseline_dir)
            visual_baseline_dir = baseline_path if baseline_path.is_absolute() else (manifest_dir / baseline_path).resolve()
    return (
        fixture_ids,
        mode,
        screenshots,
        screenshot_mode,
        screenshot_exporter,
        visual_diff,
        update_visual_baselines_flag,
        visual_mode,
        visual_threshold,
        require_visual_baselines,
        pinned_environment_required,
        visual_baseline_dir,
    )


def _scene_readiness_mode_result(
    mode: ValidationMode,
    screenshot_mode: ScreenshotExportMode,
    visual_mode: VisualRegressionMode,
    failed_fixture_count: int,
    *,
    screenshots_enabled: bool,
    visual_diff_enabled: bool,
) -> GateModeResult:
    if failed_fixture_count == 0:
        return "passed"
    if mode == "enforce" or (screenshots_enabled and screenshot_mode == "enforce") or (visual_diff_enabled and visual_mode == "enforce"):
        return "failed"
    return "issues_reported"


def _aggregate_screenshot_status(
    fixtures: list[SceneReadinessFixtureResult],
    *,
    screenshots_enabled: bool,
) -> AggregateScreenshotStatus:
    if not screenshots_enabled:
        return "disabled"
    statuses = {fixture.screenshot_export_status or "unavailable" for fixture in fixtures}
    if not statuses:
        return "unavailable"
    if "failed" in statuses:
        return "failed"
    if statuses == {"passed"}:
        return "passed"
    if statuses == {"unavailable"}:
        return "unavailable"
    return "issues_reported"


def _aggregate_visual_status(
    fixtures: list[SceneReadinessFixtureResult],
    *,
    visual_diff_enabled: bool,
) -> AggregateVisualStatus:
    if not visual_diff_enabled:
        return "disabled"
    statuses = {fixture.visual_comparison_status or "skipped" for fixture in fixtures}
    if not statuses:
        return "skipped"
    if "failed" in statuses:
        return "failed"
    if statuses == {"passed"}:
        return "passed"
    if statuses == {"skipped"}:
        return "skipped"
    return "issues_reported"


def _aggregate_object_validation_status(fixtures: list[SceneReadinessFixtureResult]) -> str:
    statuses = {fixture.object_validation_status for fixture in fixtures}
    if "failed" in statuses:
        return "failed"
    if statuses == {"passed"}:
        return "passed"
    if "issues_reported" in statuses:
        return "issues_reported"
    return "disabled" if not statuses else "issues_reported"


def _aggregate_combined_nonvisual_status(
    fixtures: list[SceneReadinessFixtureResult],
    *,
    enabled: bool,
) -> str:
    if not enabled:
        return "disabled"
    statuses = {fixture.combined_nonvisual_status for fixture in fixtures}
    if "failed" in statuses:
        return "failed"
    if statuses == {"passed"}:
        return "passed"
    return "disabled" if not statuses else "issues_reported"


def _aggregate_style_policy_status(
    fixtures: list[SceneReadinessFixtureResult],
    *,
    enabled: bool,
) -> str:
    if not enabled:
        return "disabled"
    statuses = {fixture.style_policy_status for fixture in fixtures}
    if "failed" in statuses:
        return "failed"
    if statuses == {"passed"}:
        return "passed"
    return "disabled" if not statuses else "issues_reported"


def _fixture_combined_nonvisual_findings(fixture: SceneReadinessFixtureResult) -> int:
    return fixture.validator_finding_count + len(fixture.style_policy_findings) + len(fixture.adapter_policy_findings)


def _fixture_combined_nonvisual_enforceable_count(fixture: SceneReadinessFixtureResult) -> int:
    return (
        fixture.validator_finding_count
        + fixture.style_policy_enforceable_count
        + fixture.adapter_policy_enforceable_count
    )


def _fixture_combined_nonvisual_status_from_parts(
    *,
    object_validation_status: str,
    style_policy_status: str,
    adapter_policy_status: str,
    enabled: bool,
) -> str:
    if not enabled:
        return "disabled"
    statuses = {object_validation_status, style_policy_status, adapter_policy_status}
    if "failed" in statuses:
        return "failed"
    if statuses == {"passed"}:
        return "passed"
    return "issues_reported"


def _aggregate_adapter_policy_status(
    fixtures: list[SceneReadinessFixtureResult],
    *,
    enabled: bool,
) -> str:
    if not enabled:
        return "disabled"
    statuses = {fixture.adapter_policy_status for fixture in fixtures}
    if "failed" in statuses:
        return "failed"
    if statuses == {"passed"}:
        return "passed"
    return "disabled" if not statuses else "issues_reported"


def _aggregate_adapter_quality_summary(fixtures: list[SceneReadinessFixtureResult]) -> AdapterQualitySummary:
    counts: Counter[str] = Counter()
    for fixture in fixtures:
        counts.update(fixture.adapter_quality_summary.adapter_warning_count_by_code)
    return AdapterQualitySummary(
        adapter_warning_count=sum(fixture.adapter_quality_summary.adapter_warning_count for fixture in fixtures),
        adapter_warning_count_by_code=dict(sorted(counts.items())),
        placeholder_shape_count=sum(fixture.adapter_quality_summary.placeholder_shape_count for fixture in fixtures),
        unsupported_layout_family_count=sum(
            fixture.adapter_quality_summary.unsupported_layout_family_count for fixture in fixtures
        ),
        unsupported_motif_pattern_count=sum(
            fixture.adapter_quality_summary.unsupported_motif_pattern_count for fixture in fixtures
        ),
        duplicate_object_id_resolved_count=sum(
            fixture.adapter_quality_summary.duplicate_object_id_resolved_count for fixture in fixtures
        ),
        ambiguous_mapping_count=sum(fixture.adapter_quality_summary.ambiguous_mapping_count for fixture in fixtures),
        inferred_background_shape_count=sum(
            fixture.adapter_quality_summary.inferred_background_shape_count for fixture in fixtures
        ),
        lossy_fallback_count=sum(fixture.adapter_quality_summary.lossy_fallback_count for fixture in fixtures),
    )


def _aggregate_style_quality_summary(fixtures: list[SceneReadinessFixtureResult]) -> StyleQualitySummary:
    return StyleQualitySummary(
        style_warning_count=sum(fixture.style_quality_summary.style_warning_count for fixture in fixtures),
        unresolved_theme_token_count=sum(fixture.style_quality_summary.unresolved_theme_token_count for fixture in fixtures),
        unresolved_font_token_count=sum(fixture.style_quality_summary.unresolved_font_token_count for fixture in fixtures),
        unresolved_spacing_token_count=sum(fixture.style_quality_summary.unresolved_spacing_token_count for fixture in fixtures),
        fallback_style_count=sum(fixture.style_quality_summary.fallback_style_count for fixture in fixtures),
        invalid_theme_token_count=sum(fixture.style_quality_summary.invalid_theme_token_count for fixture in fixtures),
        style_alias_count=sum(fixture.style_quality_summary.style_alias_count for fixture in fixtures),
        deprecated_style_alias_count=sum(fixture.style_quality_summary.deprecated_style_alias_count for fixture in fixtures),
        ambiguous_style_alias_count=sum(fixture.style_quality_summary.ambiguous_style_alias_count for fixture in fixtures),
        noncanonical_token_count=sum(fixture.style_quality_summary.noncanonical_token_count for fixture in fixtures),
    )


def _style_policy_for_fixture(
    style_policy: SceneStylePolicyFile | None,
    *,
    fixture_id: str,
    style_profile: str | None,
    enabled: bool,
) -> tuple[str | None, Any | None]:
    if not enabled:
        return None, None
    profile_name = style_profile or "style-strict"
    if style_policy is None:
        return profile_name, default_style_quality_policy()
    selected_profile, fixture_policy = style_policy.policy_for_fixture(fixture_id, profile_name)
    return selected_profile, fixture_policy or default_style_quality_policy()


def _adapter_policy_for_fixture(
    adapter_policy: SceneAdapterPolicyFile | None,
    *,
    fixture_id: str,
    adapter_profile: str | None,
    enabled: bool,
) -> tuple[str | None, Any | None]:
    if not enabled:
        return None, None
    profile_name = adapter_profile or "adapter-strict"
    if adapter_policy is None:
        return profile_name, default_adapter_quality_policy()
    selected_profile, fixture_policy = adapter_policy.policy_for_fixture(fixture_id, profile_name)
    return selected_profile, fixture_policy or default_adapter_quality_policy()


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
