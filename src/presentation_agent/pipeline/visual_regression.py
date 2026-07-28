"""Opt-in golden screenshot comparison for scene readiness artifacts."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import shutil
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageChops, ImageStat
from pydantic import BaseModel, ConfigDict, Field


VISUAL_REGRESSION_REPORT_VERSION = "0.1"
VISUAL_BASELINE_METADATA_VERSION = "0.1"
VisualRegressionMode = Literal["inspect", "warn", "enforce"]
VisualComparisonStatus = Literal["passed", "issues_reported", "failed", "skipped"]
VisualFindingSeverity = Literal["info", "warning", "error"]
VisualDiffFindingCode = Literal[
    "visual_baseline_missing",
    "visual_actual_missing",
    "visual_dimension_mismatch",
    "visual_diff_exceeds_threshold",
    "visual_diff_image_write_failed",
    "visual_baseline_unavailable",
    "visual_comparison_skipped",
    "visual_environment_unstable_or_unknown",
    "visual_baseline_metadata_missing",
    "visual_environment_metadata_missing",
    "visual_environment_mismatch",
    "visual_pinned_environment_required",
    "visual_baseline_refresh_required",
]
VisualThresholdPreset = Literal["lenient", "default", "strict"]


class VisualRegressionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class VisualThresholdPolicy(VisualRegressionModel):
    preset: str = "default"
    max_changed_pixel_ratio: float = 0.01
    max_mean_abs_error: float = 2.0
    max_rms_error: float = 4.0
    require_same_dimensions: bool = True
    allow_missing_baseline: bool = True
    generate_diff_images: bool = False


class VisualDiffFinding(VisualRegressionModel):
    code: VisualDiffFindingCode
    severity: VisualFindingSeverity
    message: str
    slide_number: int | None = None
    actual_path: str | None = None
    baseline_path: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class VisualDiffFindingsSummary(VisualRegressionModel):
    total_findings: int = 0
    info_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    enforceable_count: int = 0


class VisualEnvironmentMetadata(VisualRegressionModel):
    platform: str
    python_version: str
    pillow_version: str
    screenshot_exporter: str | None = None


class VisualBaselineMetadata(VisualRegressionModel):
    metadata_version: str = VISUAL_BASELINE_METADATA_VERSION
    fixture_id: str
    profile_name: str | None = None
    screenshot_exporter: str | None = None
    platform: str
    python_version: str
    pillow_version: str
    slide_count: int
    screenshot_width_px: int | None = None
    screenshot_height_px: int | None = None


class SlideVisualDiffSummary(VisualRegressionModel):
    slide_number: int
    actual_path: str
    baseline_path: str
    diff_path: str | None = None
    actual_exists: bool
    baseline_exists: bool
    width_px: int | None = None
    height_px: int | None = None
    baseline_width_px: int | None = None
    baseline_height_px: int | None = None
    changed_pixel_count: int = 0
    changed_pixel_ratio: float = 0.0
    mean_abs_error: float = 0.0
    rms_error: float = 0.0
    max_channel_delta: int = 0
    passed_threshold: bool = False
    finding_codes: list[VisualDiffFindingCode] = Field(default_factory=list)


class VisualRegressionReport(VisualRegressionModel):
    report_version: str = VISUAL_REGRESSION_REPORT_VERSION
    fixture_id: str
    mode: VisualRegressionMode
    comparison_status: VisualComparisonStatus
    pptx_path: str | None = None
    screenshot_report_path: str | None = None
    baseline_dir: str
    screenshot_dir: str
    diff_dir: str | None = None
    structural_hash: str
    slide_count_expected: int
    slide_count_compared: int = 0
    slide_count_missing_baseline: int = 0
    slide_count_missing_actual: int = 0
    threshold_failures: int = 0
    aggregate_changed_pixel_count: int = 0
    aggregate_changed_pixel_ratio: float = 0.0
    aggregate_mean_abs_error: float = 0.0
    aggregate_rms_error: float = 0.0
    threshold_policy: VisualThresholdPolicy
    environment: VisualEnvironmentMetadata
    baseline_metadata: VisualBaselineMetadata | None = None
    baseline_metadata_path: str | None = None
    findings_summary: VisualDiffFindingsSummary
    slides: list[SlideVisualDiffSummary] = Field(default_factory=list)
    findings: list[VisualDiffFinding] = Field(default_factory=list)

    def to_stable_payload(self, *, include_paths: bool = True) -> dict[str, Any]:
        return visual_regression_report_to_stable_payload(self, include_paths=include_paths)

    def to_stable_json(self) -> str:
        return visual_regression_report_to_stable_json(self)


def visual_threshold_policy_from_preset(preset: VisualThresholdPreset | str) -> VisualThresholdPolicy:
    if preset == "strict":
        return VisualThresholdPolicy(
            preset="strict",
            max_changed_pixel_ratio=0.0025,
            max_mean_abs_error=0.75,
            max_rms_error=1.5,
        )
    if preset == "lenient":
        return VisualThresholdPolicy(
            preset="lenient",
            max_changed_pixel_ratio=0.03,
            max_mean_abs_error=6.0,
            max_rms_error=10.0,
        )
    return VisualThresholdPolicy()


def compare_screenshots_to_baseline(
    *,
    fixture_id: str,
    screenshot_dir: str | Path,
    baseline_dir: str | Path,
    output_dir: str | Path,
    slide_count_expected: int,
    mode: VisualRegressionMode = "inspect",
    threshold_policy: VisualThresholdPolicy | None = None,
    require_visual_baselines: bool = False,
    write_diff_images: bool = False,
    pptx_path: str | Path | None = None,
    screenshot_report_path: str | Path | None = None,
    screenshot_exporter: str | None = None,
    profile_name: str | None = None,
    pinned_environment_required: bool = False,
    expected_screenshot_exporter: str | None = None,
) -> VisualRegressionReport:
    screenshot_root = Path(screenshot_dir).resolve()
    baseline_root = Path(baseline_dir).resolve()
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    diff_root = output_root / "visual-diffs"
    policy = threshold_policy or VisualThresholdPolicy()
    if write_diff_images:
        policy = policy.model_copy(update={"generate_diff_images": True})
        diff_root.mkdir(parents=True, exist_ok=True)

    findings: list[VisualDiffFinding] = []
    slide_summaries: list[SlideVisualDiffSummary] = []
    environment = _current_environment(screenshot_exporter=screenshot_exporter)
    baseline_metadata_path = baseline_root / "baseline-metadata.json"
    baseline_metadata: VisualBaselineMetadata | None = None
    if not baseline_root.exists():
        findings.append(
            VisualDiffFinding(
                code="visual_baseline_unavailable",
                severity="error" if require_visual_baselines else "warning",
                message="Visual baseline directory is unavailable.",
                details={"baseline_dir": str(baseline_root)},
            )
        )
    elif baseline_metadata_path.is_file():
        try:
            baseline_metadata = VisualBaselineMetadata.model_validate_json(baseline_metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:
            findings.append(
                VisualDiffFinding(
                    code="visual_environment_metadata_missing",
                    severity="error" if pinned_environment_required else "warning",
                    message="Visual baseline metadata could not be parsed.",
                    details={"error": str(exc), "baseline_metadata_path": str(baseline_metadata_path)},
                )
            )
    else:
        findings.append(
            VisualDiffFinding(
                code="visual_baseline_metadata_missing",
                severity="error" if pinned_environment_required else "info",
                message="Visual baseline metadata is missing.",
                details={"baseline_metadata_path": str(baseline_metadata_path)},
            )
        )

    if pinned_environment_required:
        findings.append(
            VisualDiffFinding(
                code="visual_pinned_environment_required",
                severity="info",
                message="Visual diff is running under a pinned-environment profile.",
                details={"profile_name": profile_name, "expected_screenshot_exporter": expected_screenshot_exporter},
            )
        )
    if expected_screenshot_exporter and screenshot_exporter and screenshot_exporter != expected_screenshot_exporter:
        findings.append(
            VisualDiffFinding(
                code="visual_environment_mismatch",
                severity="error" if pinned_environment_required else "warning",
                message="Screenshot exporter differs from the expected visual baseline policy.",
                details={"expected_screenshot_exporter": expected_screenshot_exporter, "actual_screenshot_exporter": screenshot_exporter},
            )
        )
    if baseline_metadata is not None:
        metadata_mismatches = _baseline_metadata_mismatches(baseline_metadata, environment, expected_screenshot_exporter)
        if metadata_mismatches:
            findings.append(
                VisualDiffFinding(
                    code="visual_environment_mismatch",
                    severity="error" if pinned_environment_required else "warning",
                    message="Current screenshot environment differs from baseline metadata.",
                    details={"mismatches": metadata_mismatches},
                )
            )

    for slide_number in range(1, slide_count_expected + 1):
        actual_path = screenshot_root / f"slide-{slide_number:03d}.png"
        baseline_path = baseline_root / f"slide-{slide_number:03d}.png"
        diff_path = diff_root / f"slide-{slide_number:03d}-diff.png" if write_diff_images else None
        summary, slide_findings = _compare_slide(
            slide_number=slide_number,
            actual_path=actual_path,
            baseline_path=baseline_path,
            diff_path=diff_path,
            policy=policy,
            require_visual_baselines=require_visual_baselines,
        )
        slide_summaries.append(summary)
        findings.extend(slide_findings)

    findings.append(
        VisualDiffFinding(
            code="visual_environment_unstable_or_unknown",
            severity="info",
            message="Screenshot pixel output may vary across Office/exporter versions and host environments.",
            details={"platform": platform.platform(), "screenshot_exporter": screenshot_exporter},
        )
    )
    findings = _sorted_findings(findings)
    summary = _summarize_findings(findings, require_visual_baselines=require_visual_baselines)
    report = _build_visual_regression_report(
        fixture_id=fixture_id,
        mode=mode,
        pptx_path=pptx_path,
        screenshot_report_path=screenshot_report_path,
        baseline_dir=baseline_root,
        screenshot_dir=screenshot_root,
        diff_dir=diff_root if write_diff_images else None,
        slide_count_expected=slide_count_expected,
        policy=policy,
        slides=slide_summaries,
        findings=findings,
        findings_summary=summary,
        screenshot_exporter=screenshot_exporter,
        environment=environment,
        baseline_metadata=baseline_metadata,
        baseline_metadata_path=baseline_metadata_path if baseline_metadata_path.exists() else None,
    )
    return report.model_copy(update={"structural_hash": visual_regression_report_structural_hash(report)})


def update_visual_baselines(
    *,
    screenshot_dir: str | Path,
    baseline_dir: str | Path,
    slide_count_expected: int,
    metadata: VisualBaselineMetadata | None = None,
) -> list[Path]:
    screenshot_root = Path(screenshot_dir).resolve()
    baseline_root = Path(baseline_dir).resolve()
    baseline_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for slide_number in range(1, slide_count_expected + 1):
        source = screenshot_root / f"slide-{slide_number:03d}.png"
        if not source.is_file():
            continue
        destination = baseline_root / source.name
        shutil.copyfile(source, destination)
        written.append(destination)
    if metadata is not None:
        (baseline_root / "baseline-metadata.json").write_text(
            json.dumps(_normalize_for_stable_json(metadata.model_dump(mode="json", exclude_none=True)), sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    return written


def build_visual_baseline_metadata(
    *,
    fixture_id: str,
    screenshot_dir: str | Path,
    slide_count: int,
    profile_name: str | None = None,
    screenshot_exporter: str | None = None,
) -> VisualBaselineMetadata:
    screenshot_root = Path(screenshot_dir)
    first_slide = screenshot_root / "slide-001.png"
    width_px: int | None = None
    height_px: int | None = None
    if first_slide.is_file():
        try:
            with Image.open(first_slide) as image:
                width_px, height_px = image.size
        except Exception:
            width_px = None
            height_px = None
    environment = _current_environment(screenshot_exporter=screenshot_exporter)
    return VisualBaselineMetadata(
        fixture_id=fixture_id,
        profile_name=profile_name,
        screenshot_exporter=screenshot_exporter,
        platform=environment.platform,
        python_version=environment.python_version,
        pillow_version=environment.pillow_version,
        slide_count=slide_count,
        screenshot_width_px=width_px,
        screenshot_height_px=height_px,
    )


def write_visual_regression_report(report: VisualRegressionReport, output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(visual_regression_report_to_stable_json(report) + "\n", encoding="utf-8")
    return destination


def summarize_visual_regression_report(report: VisualRegressionReport) -> list[str]:
    return [
        "VISUAL_REGRESSION "
        f"fixture={report.fixture_id} "
        f"status={report.comparison_status} "
        f"compared={report.slide_count_compared} "
        f"missing_baselines={report.slide_count_missing_baseline} "
        f"threshold_failures={report.threshold_failures} "
        f"findings={report.findings_summary.total_findings} "
        f"warnings={report.findings_summary.warning_count} "
        f"errors={report.findings_summary.error_count}"
    ]


def visual_regression_report_to_stable_payload(
    report: VisualRegressionReport,
    *,
    include_paths: bool = True,
) -> dict[str, Any]:
    payload = report.model_dump(mode="json", exclude_none=True)
    if not include_paths:
        for key in ("pptx_path", "screenshot_report_path", "baseline_dir", "screenshot_dir", "diff_dir", "baseline_metadata_path"):
            payload.pop(key, None)
        for slide in payload.get("slides", []):
            slide.pop("actual_path", None)
            slide.pop("baseline_path", None)
            slide.pop("diff_path", None)
        for finding in payload.get("findings", []):
            finding.pop("actual_path", None)
            finding.pop("baseline_path", None)
    return _normalize_for_stable_json(payload)


def visual_regression_report_to_stable_json(report: VisualRegressionReport) -> str:
    return json.dumps(visual_regression_report_to_stable_payload(report), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def visual_regression_report_structural_hash(report: VisualRegressionReport) -> str:
    payload = visual_regression_report_to_stable_payload(report, include_paths=False)
    payload.pop("structural_hash", None)
    stable_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


def _compare_slide(
    *,
    slide_number: int,
    actual_path: Path,
    baseline_path: Path,
    diff_path: Path | None,
    policy: VisualThresholdPolicy,
    require_visual_baselines: bool,
) -> tuple[SlideVisualDiffSummary, list[VisualDiffFinding]]:
    findings: list[VisualDiffFinding] = []
    actual_exists = actual_path.is_file()
    baseline_exists = baseline_path.is_file()
    if not actual_exists:
        findings.append(
            VisualDiffFinding(
                code="visual_actual_missing",
                severity="error",
                message="Actual screenshot is missing.",
                slide_number=slide_number,
                actual_path=str(actual_path),
            )
        )
    if not baseline_exists:
        findings.append(
            VisualDiffFinding(
                code="visual_baseline_missing",
                severity="error" if require_visual_baselines else "warning",
                message="Visual baseline screenshot is missing.",
                slide_number=slide_number,
                baseline_path=str(baseline_path),
            )
        )
    if not actual_exists or not baseline_exists:
        return (
            SlideVisualDiffSummary(
                slide_number=slide_number,
                actual_path=str(actual_path),
                baseline_path=str(baseline_path),
                diff_path=str(diff_path) if diff_path is not None else None,
                actual_exists=actual_exists,
                baseline_exists=baseline_exists,
                finding_codes=[finding.code for finding in findings],
            ),
            findings,
        )

    try:
        with Image.open(actual_path) as actual_image, Image.open(baseline_path) as baseline_image:
            actual = actual_image.convert("RGB")
            baseline = baseline_image.convert("RGB")
            actual_width, actual_height = actual.size
            baseline_width, baseline_height = baseline.size
            if actual.size != baseline.size:
                findings.append(
                    VisualDiffFinding(
                        code="visual_dimension_mismatch",
                        severity="error" if policy.require_same_dimensions else "warning",
                        message="Actual screenshot dimensions differ from baseline.",
                        slide_number=slide_number,
                        actual_path=str(actual_path),
                        baseline_path=str(baseline_path),
                        details={
                            "actual_width_px": actual_width,
                            "actual_height_px": actual_height,
                            "baseline_width_px": baseline_width,
                            "baseline_height_px": baseline_height,
                        },
                    )
                )
                return (
                    SlideVisualDiffSummary(
                        slide_number=slide_number,
                        actual_path=str(actual_path),
                        baseline_path=str(baseline_path),
                        diff_path=str(diff_path) if diff_path is not None else None,
                        actual_exists=True,
                        baseline_exists=True,
                        width_px=actual_width,
                        height_px=actual_height,
                        baseline_width_px=baseline_width,
                        baseline_height_px=baseline_height,
                        passed_threshold=not policy.require_same_dimensions,
                        finding_codes=[finding.code for finding in findings],
                    ),
                    findings,
                )
            diff = ImageChops.difference(actual, baseline)
            diff_luminance = diff.convert("L")
            histogram = diff_luminance.histogram()
            changed_pixel_count = sum(histogram[1:])
            total_pixels = actual_width * actual_height
            changed_pixel_ratio = changed_pixel_count / float(total_pixels) if total_pixels else 0.0
            stats = ImageStat.Stat(diff)
            mean_abs_error = sum(float(value) for value in stats.mean) / len(stats.mean)
            rms_error = math.sqrt(sum(float(value) ** 2 for value in stats.rms) / len(stats.rms))
            max_channel_delta = max(max(channel_extrema) for channel_extrema in diff.getextrema())
            exceeds = (
                changed_pixel_ratio > policy.max_changed_pixel_ratio
                or mean_abs_error > policy.max_mean_abs_error
                or rms_error > policy.max_rms_error
            )
            if exceeds:
                findings.append(
                    VisualDiffFinding(
                        code="visual_diff_exceeds_threshold",
                        severity="error",
                        message="Visual difference exceeds configured threshold.",
                        slide_number=slide_number,
                        actual_path=str(actual_path),
                        baseline_path=str(baseline_path),
                        details={
                            "changed_pixel_ratio": round(changed_pixel_ratio, 8),
                            "max_changed_pixel_ratio": policy.max_changed_pixel_ratio,
                            "mean_abs_error": round(mean_abs_error, 6),
                            "max_mean_abs_error": policy.max_mean_abs_error,
                            "rms_error": round(rms_error, 6),
                            "max_rms_error": policy.max_rms_error,
                        },
                    )
                )
            if diff_path is not None:
                try:
                    diff.save(diff_path)
                except Exception as exc:
                    findings.append(
                        VisualDiffFinding(
                            code="visual_diff_image_write_failed",
                            severity="warning",
                            message="Visual diff image could not be written.",
                            slide_number=slide_number,
                            actual_path=str(actual_path),
                            baseline_path=str(baseline_path),
                            details={"error": str(exc)},
                        )
                    )
            return (
                SlideVisualDiffSummary(
                    slide_number=slide_number,
                    actual_path=str(actual_path),
                    baseline_path=str(baseline_path),
                    diff_path=str(diff_path) if diff_path is not None else None,
                    actual_exists=True,
                    baseline_exists=True,
                    width_px=actual_width,
                    height_px=actual_height,
                    baseline_width_px=baseline_width,
                    baseline_height_px=baseline_height,
                    changed_pixel_count=changed_pixel_count,
                    changed_pixel_ratio=changed_pixel_ratio,
                    mean_abs_error=mean_abs_error,
                    rms_error=rms_error,
                    max_channel_delta=max_channel_delta,
                    passed_threshold=not exceeds,
                    finding_codes=[finding.code for finding in findings],
                ),
                findings,
            )
    except Exception as exc:
        findings.append(
            VisualDiffFinding(
                code="visual_comparison_skipped",
                severity="error",
                message="Visual comparison could not open screenshot inputs.",
                slide_number=slide_number,
                actual_path=str(actual_path),
                baseline_path=str(baseline_path),
                details={"error": str(exc)},
            )
        )
        return (
            SlideVisualDiffSummary(
                slide_number=slide_number,
                actual_path=str(actual_path),
                baseline_path=str(baseline_path),
                diff_path=str(diff_path) if diff_path is not None else None,
                actual_exists=True,
                baseline_exists=True,
                finding_codes=[finding.code for finding in findings],
            ),
            findings,
        )


def _build_visual_regression_report(
    *,
    fixture_id: str,
    mode: VisualRegressionMode,
    pptx_path: str | Path | None,
    screenshot_report_path: str | Path | None,
    baseline_dir: Path,
    screenshot_dir: Path,
    diff_dir: Path | None,
    slide_count_expected: int,
    policy: VisualThresholdPolicy,
    slides: list[SlideVisualDiffSummary],
    findings: list[VisualDiffFinding],
    findings_summary: VisualDiffFindingsSummary,
    screenshot_exporter: str | None,
    environment: VisualEnvironmentMetadata,
    baseline_metadata: VisualBaselineMetadata | None,
    baseline_metadata_path: Path | None,
) -> VisualRegressionReport:
    compared = [slide for slide in slides if slide.actual_exists and slide.baseline_exists and slide.width_px and slide.baseline_width_px]
    total_pixels = sum((slide.width_px or 0) * (slide.height_px or 0) for slide in compared)
    changed_pixels = sum(slide.changed_pixel_count for slide in compared)
    aggregate_mean = sum(slide.mean_abs_error for slide in compared) / len(compared) if compared else 0.0
    aggregate_rms = math.sqrt(sum(slide.rms_error ** 2 for slide in compared) / len(compared)) if compared else 0.0
    threshold_failures = sum(1 for slide in slides if "visual_diff_exceeds_threshold" in slide.finding_codes)
    comparison_status = _comparison_status(mode, findings_summary)
    return VisualRegressionReport(
        fixture_id=fixture_id,
        mode=mode,
        comparison_status=comparison_status,
        pptx_path=str(pptx_path) if pptx_path is not None else None,
        screenshot_report_path=str(screenshot_report_path) if screenshot_report_path is not None else None,
        baseline_dir=str(baseline_dir),
        screenshot_dir=str(screenshot_dir),
        diff_dir=str(diff_dir) if diff_dir is not None else None,
        structural_hash="",
        slide_count_expected=slide_count_expected,
        slide_count_compared=len(compared),
        slide_count_missing_baseline=sum(1 for slide in slides if not slide.baseline_exists),
        slide_count_missing_actual=sum(1 for slide in slides if not slide.actual_exists),
        threshold_failures=threshold_failures,
        aggregate_changed_pixel_count=changed_pixels,
        aggregate_changed_pixel_ratio=changed_pixels / float(total_pixels) if total_pixels else 0.0,
        aggregate_mean_abs_error=aggregate_mean,
        aggregate_rms_error=aggregate_rms,
        threshold_policy=policy,
        environment=environment,
        baseline_metadata=baseline_metadata,
        baseline_metadata_path=str(baseline_metadata_path) if baseline_metadata_path is not None else None,
        findings_summary=findings_summary,
        slides=slides,
        findings=findings,
    )


def _summarize_findings(
    findings: list[VisualDiffFinding],
    *,
    require_visual_baselines: bool,
) -> VisualDiffFindingsSummary:
    info_count = sum(1 for finding in findings if finding.severity == "info")
    warning_count = sum(1 for finding in findings if finding.severity == "warning")
    error_count = sum(1 for finding in findings if finding.severity == "error")
    enforceable_count = 0
    for finding in findings:
        if finding.severity == "error":
            enforceable_count += 1
        elif finding.code == "visual_baseline_missing" and require_visual_baselines:
            enforceable_count += 1
    return VisualDiffFindingsSummary(
        total_findings=len(findings),
        info_count=info_count,
        warning_count=warning_count,
        error_count=error_count,
        enforceable_count=enforceable_count,
    )


def _comparison_status(mode: VisualRegressionMode, summary: VisualDiffFindingsSummary) -> VisualComparisonStatus:
    if mode == "enforce" and summary.enforceable_count > 0:
        return "failed"
    if summary.warning_count + summary.error_count > 0:
        return "issues_reported"
    return "passed"


def _current_environment(*, screenshot_exporter: str | None) -> VisualEnvironmentMetadata:
    return VisualEnvironmentMetadata(
        platform=platform.platform(),
        python_version=platform.python_version(),
        pillow_version=Image.__version__,
        screenshot_exporter=screenshot_exporter,
    )


def _baseline_metadata_mismatches(
    baseline_metadata: VisualBaselineMetadata,
    environment: VisualEnvironmentMetadata,
    expected_screenshot_exporter: str | None,
) -> dict[str, dict[str, str | None]]:
    mismatches: dict[str, dict[str, str | None]] = {}
    checks = {
        "platform": (baseline_metadata.platform, environment.platform),
        "python_version": (baseline_metadata.python_version, environment.python_version),
        "pillow_version": (baseline_metadata.pillow_version, environment.pillow_version),
        "screenshot_exporter": (baseline_metadata.screenshot_exporter, expected_screenshot_exporter or environment.screenshot_exporter),
    }
    for key, (baseline_value, current_value) in checks.items():
        if baseline_value != current_value:
            mismatches[key] = {"baseline": baseline_value, "current": current_value}
    return mismatches


def _sorted_findings(findings: list[VisualDiffFinding]) -> list[VisualDiffFinding]:
    return sorted(
        findings,
        key=lambda finding: (
            -1 if finding.slide_number is None else finding.slide_number,
            finding.code,
            finding.severity,
            finding.message,
            finding.actual_path or "",
            finding.baseline_path or "",
        ),
    )


def _normalize_for_stable_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_for_stable_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize_for_stable_json(item) for item in value]
    if isinstance(value, float):
        normalized = round(value, 8)
        if normalized == 0:
            return 0
        if float(normalized).is_integer():
            return int(normalized)
        return normalized
    return value
