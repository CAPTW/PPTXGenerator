"""Opt-in screenshot export and visual sanity reporting for compiled PPTX files."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Literal

from PIL import Image, ImageStat
from pydantic import BaseModel, ConfigDict, Field


SCREENSHOT_EXPORT_REPORT_VERSION = "0.1"
ScreenshotExportMode = Literal["inspect", "warn", "enforce"]
ScreenshotExporterName = Literal["auto", "powerpoint", "libreoffice", "none"]
ScreenshotOutputFormat = Literal["png"]
ScreenshotExportStatus = Literal["passed", "issues_reported", "failed", "unavailable"]
VisualQaSeverity = Literal["info", "warning", "error"]
VisualQaFindingCode = Literal[
    "screenshot_exporter_unavailable",
    "screenshot_export_failed",
    "screenshot_slide_count_mismatch",
    "screenshot_file_missing",
    "screenshot_file_empty",
    "screenshot_dimension_mismatch",
    "screenshot_blank_or_near_blank",
    "screenshot_unexpected_aspect_ratio",
]
_ASPECT_RATIO_16_9 = 16.0 / 9.0
_ASPECT_RATIO_TOLERANCE = 0.08
_BLANK_STDDEV_THRESHOLD = 1.0
_BLANK_LUMINANCE_HIGH = 250.0
_BLANK_LUMINANCE_LOW = 5.0


class ScreenshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ScreenshotExporterDetection(ScreenshotModel):
    requested_exporter: ScreenshotExporterName
    exporter: str
    exporter_available: bool
    reason: str | None = None


class VisualQaFinding(ScreenshotModel):
    code: VisualQaFindingCode
    severity: VisualQaSeverity
    message: str
    slide_number: int | None = None
    screenshot_path: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class VisualQaFindingsSummary(ScreenshotModel):
    total_findings: int
    info_count: int
    warning_count: int
    error_count: int
    enforceable_count: int


class SlideScreenshotSummary(ScreenshotModel):
    slide_number: int
    screenshot_path: str
    file_exists: bool
    file_size_bytes: int = 0
    width_px: int | None = None
    height_px: int | None = None
    mean_luminance: float | None = None
    stddev_luminance: float | None = None


class ScreenshotExportReport(ScreenshotModel):
    report_version: str = SCREENSHOT_EXPORT_REPORT_VERSION
    mode: ScreenshotExportMode
    requested_exporter: ScreenshotExporterName
    exporter: str
    exporter_available: bool
    export_status: ScreenshotExportStatus
    pptx_path: str
    output_dir: str
    output_format: ScreenshotOutputFormat = "png"
    structural_hash: str
    slide_count_expected: int
    slide_count_exported: int
    screenshots_exported: int
    findings_summary: VisualQaFindingsSummary
    slides: list[SlideScreenshotSummary] = Field(default_factory=list)
    findings: list[VisualQaFinding] = Field(default_factory=list)

    def to_stable_payload(self, *, include_paths: bool = True) -> dict[str, Any]:
        return screenshot_export_report_to_stable_payload(self, include_paths=include_paths)

    def to_stable_json(self) -> str:
        return screenshot_export_report_to_stable_json(self)


ScreenshotExportImplementation = Callable[[Path, Path, ScreenshotOutputFormat], list[Path]]


def detect_screenshot_exporter(exporter: ScreenshotExporterName = "auto") -> ScreenshotExporterDetection:
    if exporter == "none":
        return ScreenshotExporterDetection(
            requested_exporter=exporter,
            exporter="none",
            exporter_available=False,
            reason="Screenshot export explicitly disabled.",
        )
    if exporter == "libreoffice":
        return ScreenshotExporterDetection(
            requested_exporter=exporter,
            exporter="libreoffice",
            exporter_available=False,
            reason="LibreOffice screenshot export is not implemented in this repo yet.",
        )
    if exporter == "powerpoint":
        return _detect_powerpoint_exporter(requested_exporter=exporter)
    powerpoint = _detect_powerpoint_exporter(requested_exporter=exporter)
    if powerpoint.exporter_available:
        return powerpoint
    return ScreenshotExporterDetection(
        requested_exporter=exporter,
        exporter="none",
        exporter_available=False,
        reason=powerpoint.reason or "No supported screenshot exporter is available.",
    )


def export_pptx_screenshots(
    pptx_path: str | Path,
    *,
    output_dir: str | Path,
    slide_count_expected: int,
    mode: ScreenshotExportMode = "inspect",
    exporter: ScreenshotExporterName = "auto",
    output_format: ScreenshotOutputFormat = "png",
    export_impl: ScreenshotExportImplementation | None = None,
    detection_override: ScreenshotExporterDetection | None = None,
) -> ScreenshotExportReport:
    pptx_file = Path(pptx_path).resolve()
    export_dir = Path(output_dir).resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    detection = detection_override or detect_screenshot_exporter(exporter)
    findings: list[VisualQaFinding] = []
    exported_paths: list[Path] = []

    if not detection.exporter_available:
        findings.append(
            VisualQaFinding(
                code="screenshot_exporter_unavailable",
                severity="warning",
                message=detection.reason or "No screenshot exporter is available.",
                details={"requested_exporter": detection.requested_exporter, "exporter": detection.exporter},
            )
        )
        report = _build_screenshot_export_report(
            pptx_path=pptx_file,
            output_dir=export_dir,
            slide_count_expected=slide_count_expected,
            mode=mode,
            detection=detection,
            output_format=output_format,
            exported_paths=[],
            findings=findings,
        )
        return report

    implementation = export_impl or _resolve_export_implementation(detection.exporter)
    if implementation is None:
        findings.append(
            VisualQaFinding(
                code="screenshot_exporter_unavailable",
                severity="warning",
                message=f"Exporter {detection.exporter!r} is detected but not wired to an implementation.",
                details={"requested_exporter": detection.requested_exporter, "exporter": detection.exporter},
            )
        )
        return _build_screenshot_export_report(
            pptx_path=pptx_file,
            output_dir=export_dir,
            slide_count_expected=slide_count_expected,
            mode=mode,
            detection=detection.model_copy(update={"exporter_available": False}),
            output_format=output_format,
            exported_paths=[],
            findings=findings,
        )

    _clear_export_dir(export_dir, output_format=output_format)
    try:
        exported_paths = implementation(pptx_file, export_dir, output_format)
    except Exception as exc:
        findings.append(
            VisualQaFinding(
                code="screenshot_export_failed",
                severity="error",
                message="Screenshot export failed.",
                details={"error": str(exc), "exporter": detection.exporter},
            )
        )
        exported_paths = []

    return _build_screenshot_export_report(
        pptx_path=pptx_file,
        output_dir=export_dir,
        slide_count_expected=slide_count_expected,
        mode=mode,
        detection=detection,
        output_format=output_format,
        exported_paths=exported_paths,
        findings=findings,
    )


def write_screenshot_export_report(report: ScreenshotExportReport, output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(screenshot_export_report_to_stable_json(report) + "\n", encoding="utf-8")
    return destination


def summarize_screenshot_export_report(report: ScreenshotExportReport) -> list[str]:
    return [
        "SCREENSHOT_EXPORT "
        f"exporter={report.exporter} "
        f"status={report.export_status} "
        f"slides={report.slide_count_expected} "
        f"exported={report.slide_count_exported} "
        f"findings={report.findings_summary.total_findings} "
        f"warnings={report.findings_summary.warning_count} "
        f"errors={report.findings_summary.error_count}"
    ]


def screenshot_export_report_to_stable_payload(
    report: ScreenshotExportReport,
    *,
    include_paths: bool = True,
) -> dict[str, Any]:
    payload = report.model_dump(mode="json", exclude_none=True)
    if not include_paths:
        payload.pop("pptx_path", None)
        payload.pop("output_dir", None)
        for slide in payload.get("slides", []):
            slide.pop("screenshot_path", None)
        for finding in payload.get("findings", []):
            finding.pop("screenshot_path", None)
    return _normalize_for_stable_json(payload)


def screenshot_export_report_to_stable_json(report: ScreenshotExportReport) -> str:
    return json.dumps(screenshot_export_report_to_stable_payload(report), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def screenshot_export_report_structural_hash(report: ScreenshotExportReport) -> str:
    payload = screenshot_export_report_to_stable_payload(report, include_paths=False)
    payload.pop("structural_hash", None)
    stable_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


def _build_screenshot_export_report(
    *,
    pptx_path: Path,
    output_dir: Path,
    slide_count_expected: int,
    mode: ScreenshotExportMode,
    detection: ScreenshotExporterDetection,
    output_format: ScreenshotOutputFormat,
    exported_paths: list[Path],
    findings: list[VisualQaFinding],
) -> ScreenshotExportReport:
    slide_summaries: list[SlideScreenshotSummary] = []
    exported_paths_by_slide = {index + 1: path.resolve() for index, path in enumerate(_sorted_export_paths(exported_paths))}
    reference_dimensions: tuple[int, int] | None = None

    if detection.exporter_available and len(exported_paths_by_slide) != slide_count_expected:
        findings.append(
            VisualQaFinding(
                code="screenshot_slide_count_mismatch",
                severity="error",
                message="Screenshot export did not produce the expected number of slide images.",
                details={"expected": slide_count_expected, "actual": len(exported_paths_by_slide)},
            )
        )

    for slide_number in range(1, slide_count_expected + 1):
        screenshot_path = exported_paths_by_slide.get(slide_number, (output_dir / f"slide-{slide_number:03d}.{output_format}").resolve())
        summary, screenshot_findings = _inspect_screenshot_file(
            slide_number,
            screenshot_path,
            reference_dimensions=reference_dimensions,
        )
        if summary.width_px and summary.height_px and reference_dimensions is None:
            reference_dimensions = (summary.width_px, summary.height_px)
        slide_summaries.append(summary)
        findings.extend(screenshot_findings)

    findings = _sorted_findings(findings)
    findings_summary = _summarize_findings(findings)
    export_status = _screenshot_export_status(mode, findings_summary, detection.exporter_available)
    report = ScreenshotExportReport(
        mode=mode,
        requested_exporter=detection.requested_exporter,
        exporter=detection.exporter,
        exporter_available=detection.exporter_available,
        export_status=export_status,
        pptx_path=str(pptx_path),
        output_dir=str(output_dir),
        output_format=output_format,
        structural_hash="",
        slide_count_expected=slide_count_expected,
        slide_count_exported=sum(1 for slide in slide_summaries if slide.file_exists),
        screenshots_exported=sum(1 for slide in slide_summaries if slide.file_exists),
        findings_summary=findings_summary,
        slides=slide_summaries,
        findings=findings,
    )
    return report.model_copy(update={"structural_hash": screenshot_export_report_structural_hash(report)})


def _inspect_screenshot_file(
    slide_number: int,
    screenshot_path: Path,
    *,
    reference_dimensions: tuple[int, int] | None,
) -> tuple[SlideScreenshotSummary, list[VisualQaFinding]]:
    findings: list[VisualQaFinding] = []
    file_exists = screenshot_path.is_file()
    file_size = screenshot_path.stat().st_size if file_exists else 0
    width_px: int | None = None
    height_px: int | None = None
    mean_luminance: float | None = None
    stddev_luminance: float | None = None

    if not file_exists:
        findings.append(
            VisualQaFinding(
                code="screenshot_file_missing",
                severity="error",
                slide_number=slide_number,
                screenshot_path=str(screenshot_path),
                message="Expected screenshot file is missing.",
            )
        )
    elif file_size <= 0:
        findings.append(
            VisualQaFinding(
                code="screenshot_file_empty",
                severity="error",
                slide_number=slide_number,
                screenshot_path=str(screenshot_path),
                message="Screenshot file exists but is empty.",
            )
        )
    else:
        try:
            with Image.open(screenshot_path) as image:
                width_px, height_px = image.size
                grayscale = image.convert("L")
                stats = ImageStat.Stat(grayscale)
                mean_luminance = float(stats.mean[0])
                stddev_luminance = float(stats.stddev[0])
        except Exception as exc:
            findings.append(
                VisualQaFinding(
                    code="screenshot_export_failed",
                    severity="error",
                    slide_number=slide_number,
                    screenshot_path=str(screenshot_path),
                    message="Screenshot file could not be opened for sanity inspection.",
                    details={"error": str(exc)},
                )
            )
        else:
            if width_px is None or height_px is None or width_px <= 0 or height_px <= 0:
                findings.append(
                    VisualQaFinding(
                        code="screenshot_dimension_mismatch",
                        severity="error",
                        slide_number=slide_number,
                        screenshot_path=str(screenshot_path),
                        message="Screenshot dimensions are invalid.",
                        details={"width_px": width_px, "height_px": height_px},
                    )
                )
            else:
                if reference_dimensions is not None and (width_px, height_px) != reference_dimensions:
                    findings.append(
                        VisualQaFinding(
                            code="screenshot_dimension_mismatch",
                            severity="warning",
                            slide_number=slide_number,
                            screenshot_path=str(screenshot_path),
                            message="Screenshot dimensions differ from the first exported slide.",
                            details={
                                "expected_width_px": reference_dimensions[0],
                                "expected_height_px": reference_dimensions[1],
                                "actual_width_px": width_px,
                                "actual_height_px": height_px,
                            },
                        )
                    )
                aspect_ratio = width_px / float(height_px)
                if abs(aspect_ratio - _ASPECT_RATIO_16_9) > _ASPECT_RATIO_TOLERANCE:
                    findings.append(
                        VisualQaFinding(
                            code="screenshot_unexpected_aspect_ratio",
                            severity="warning",
                            slide_number=slide_number,
                            screenshot_path=str(screenshot_path),
                            message="Screenshot aspect ratio is outside the expected 16:9 tolerance band.",
                            details={"aspect_ratio": round(aspect_ratio, 6), "expected_aspect_ratio": round(_ASPECT_RATIO_16_9, 6)},
                        )
                    )
                if (
                    mean_luminance is not None
                    and stddev_luminance is not None
                    and stddev_luminance <= _BLANK_STDDEV_THRESHOLD
                    and (mean_luminance >= _BLANK_LUMINANCE_HIGH or mean_luminance <= _BLANK_LUMINANCE_LOW)
                ):
                    findings.append(
                        VisualQaFinding(
                            code="screenshot_blank_or_near_blank",
                            severity="warning",
                            slide_number=slide_number,
                            screenshot_path=str(screenshot_path),
                            message="Screenshot appears blank or near-blank under a conservative luminance heuristic.",
                            details={
                                "mean_luminance": round(mean_luminance, 4),
                                "stddev_luminance": round(stddev_luminance, 4),
                            },
                        )
                    )

    summary = SlideScreenshotSummary(
        slide_number=slide_number,
        screenshot_path=str(screenshot_path),
        file_exists=file_exists,
        file_size_bytes=file_size,
        width_px=width_px,
        height_px=height_px,
        mean_luminance=mean_luminance,
        stddev_luminance=stddev_luminance,
    )
    return summary, findings


def _sorted_export_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return sorted(unique, key=lambda path: (_slide_index_from_path(path), path.name.lower()))


def _slide_index_from_path(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 10_000


def _detect_powerpoint_exporter(*, requested_exporter: ScreenshotExporterName) -> ScreenshotExporterDetection:
    try:  # pragma: no cover - depends on local Windows/PPT availability
        import pythoncom
        import win32com.client
    except Exception as exc:  # pragma: no cover
        return ScreenshotExporterDetection(
            requested_exporter=requested_exporter,
            exporter="powerpoint",
            exporter_available=False,
            reason=f"PowerPoint COM dependencies are unavailable: {exc}",
        )
    application = None
    pythoncom.CoInitialize()
    try:  # pragma: no cover - depends on local Windows/PPT availability
        application = win32com.client.DispatchEx("PowerPoint.Application")
        return ScreenshotExporterDetection(
            requested_exporter=requested_exporter,
            exporter="powerpoint",
            exporter_available=True,
        )
    except Exception as exc:  # pragma: no cover
        return ScreenshotExporterDetection(
            requested_exporter=requested_exporter,
            exporter="powerpoint",
            exporter_available=False,
            reason=f"PowerPoint COM export is unavailable: {exc}",
        )
    finally:  # pragma: no cover
        if application is not None:
            try:
                application.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _resolve_export_implementation(exporter: str) -> ScreenshotExportImplementation | None:
    if exporter == "powerpoint":
        return _export_with_powerpoint
    return None


def _export_with_powerpoint(pptx_path: Path, output_dir: Path, output_format: ScreenshotOutputFormat) -> list[Path]:
    try:  # pragma: no cover - depends on local PowerPoint availability
        import pythoncom
        import win32com.client
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"PowerPoint COM dependencies are unavailable: {exc}") from exc

    application = None
    deck = None
    pythoncom.CoInitialize()
    try:  # pragma: no cover - manual/integration only
        output_dir.mkdir(parents=True, exist_ok=True)
        application = win32com.client.DispatchEx("PowerPoint.Application")
        application.Visible = 1
        deck = application.Presentations.Open(str(pptx_path), WithWindow=False)
        deck.Export(str(output_dir), output_format.upper(), 1280, 720)
    finally:  # pragma: no cover
        if deck is not None:
            try:
                deck.Close()
            except Exception:
                pass
        if application is not None:
            try:
                application.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

    exported = _sorted_export_paths(list(output_dir.glob(f"*.{output_format}")) + list(output_dir.glob(f"*.{output_format.upper()}")))
    normalized_paths: list[Path] = []
    for index, source_path in enumerate(exported, start=1):
        target_path = output_dir / f"slide-{index:03d}.{output_format}"
        if source_path.resolve() != target_path.resolve():
            if target_path.exists():
                target_path.unlink()
            source_path.replace(target_path)
        normalized_paths.append(target_path)
    return normalized_paths


def _clear_export_dir(output_dir: Path, *, output_format: ScreenshotOutputFormat) -> None:
    for path in _sorted_export_paths(
        list(output_dir.glob(f"*.{output_format}")) + list(output_dir.glob(f"*.{output_format.upper()}"))
    ):
        path.unlink()


def _sorted_findings(findings: list[VisualQaFinding]) -> list[VisualQaFinding]:
    return sorted(
        findings,
        key=lambda item: (
            -1 if item.slide_number is None else item.slide_number,
            item.code,
            item.severity,
            item.message,
            item.screenshot_path or "",
        ),
    )


def _summarize_findings(findings: list[VisualQaFinding]) -> VisualQaFindingsSummary:
    info_count = sum(1 for finding in findings if finding.severity == "info")
    warning_count = sum(1 for finding in findings if finding.severity == "warning")
    error_count = sum(1 for finding in findings if finding.severity == "error")
    return VisualQaFindingsSummary(
        total_findings=len(findings),
        info_count=info_count,
        warning_count=warning_count,
        error_count=error_count,
        enforceable_count=warning_count + error_count,
    )


def _screenshot_export_status(
    mode: ScreenshotExportMode,
    summary: VisualQaFindingsSummary,
    exporter_available: bool,
) -> ScreenshotExportStatus:
    if not exporter_available:
        return "unavailable"
    if mode == "enforce" and summary.enforceable_count > 0:
        return "failed"
    if summary.total_findings > 0:
        return "issues_reported"
    return "passed"


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
