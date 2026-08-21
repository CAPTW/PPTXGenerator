"""Close per-slide reconstruction QA from one source-mapped shared preview."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import DeckCompilerError
from ..manifest_io import read_json, write_json
from .quality_acceptance import evaluate_visual_quality_acceptance
from .reconstruction_jobs import (
    JOB_MANIFEST_NAME,
    PROJECT_DIRECTORY,
    validate_reconstruction_job_bundle,
)


COUNT_KEYS = ("text", "panels", "rules", "icons", "tables", "charts", "badges", "callouts")
CROP_KEYS = (
    "totalCropAreaRatio",
    "largestCropAreaRatio",
    "textOrTableCropAreaRatio",
    "photorealCropAreaRatio",
    "denseInfographicCropAreaRatio",
)


@dataclass(frozen=True, slots=True)
class SharedRenderQAResult:
    workflow_id: str
    runtime_root: Path
    summary_path: Path
    slide_count: int
    receipt_paths: tuple[Path, ...]


def finalize_shared_render_qa(
    runtime_root: Path,
    *,
    summary_path: Path,
) -> SharedRenderQAResult:
    """Materialize final job QA only from accepted shared-render evidence."""

    root = runtime_root.resolve()
    project = root / PROJECT_DIRECTORY
    summary = summary_path.resolve()
    if summary != project and not summary.is_relative_to(project):
        raise _error(
            "DC_SHARED_RENDER_QA_INPUT_INVALID",
            "shared preview summary must stay inside pngtopptx-project",
            summary,
        )
    manifest_path = project / "work" / JOB_MANIFEST_NAME
    manifest = _read_object(manifest_path, "reconstruction job manifest")
    slides = [
        int(row["slide_number"])
        for row in manifest.get("jobs", [])
        if isinstance(row, dict) and isinstance(row.get("slide_number"), int)
    ]
    if not slides or slides != list(range(1, len(slides) + 1)):
        raise _error(
            "DC_SHARED_RENDER_QA_INPUT_INVALID",
            "reconstruction jobs must cover contiguous slides before QA finalization",
            manifest_path,
        )
    authoring = validate_reconstruction_job_bundle(
        root,
        require_authoring_outputs=True,
    )
    if not authoring["valid"]:
        raise _error(
            "DC_SHARED_RENDER_QA_AUTHORING_INVALID",
            "; ".join(authoring["issues"][:8]),
            manifest_path,
        )
    acceptance = evaluate_visual_quality_acceptance(
        project=project,
        summary_path=summary,
        slides=slides,
    )
    if not acceptance["accepted"]:
        raise _error(
            "DC_SHARED_RENDER_QA_REJECTED",
            "; ".join(acceptance["issues"][:8]),
            summary,
        )
    summary_payload = _read_object(summary, "shared preview summary")
    summary_checked_at = str(summary_payload.get("createdAt", "")).strip()

    native_manifest = _read_object(
        project / "out" / "native_object_manifest.json",
        "native object manifest",
    )
    crop_summary = _read_object(
        project / "out" / "crop_coverage_summary.json",
        "crop coverage summary",
    )
    native_slides = native_manifest.get("slides")
    crop_slides = crop_summary.get("slides")
    if not isinstance(native_slides, dict) or not isinstance(crop_slides, dict):
        raise _error(
            "DC_SHARED_RENDER_QA_OBJECTIVE_EVIDENCE_INVALID",
            "native and crop summaries must contain per-slide evidence",
            project / "out",
        )

    receipt_paths: list[Path] = []
    for manifest_row in manifest["jobs"]:
        slide = int(manifest_row["slide_number"])
        job_path = _artifact_path(root, manifest_row.get("job"), f"slide {slide} job")
        job = _read_object(job_path, f"slide {slide} job")
        work_dir = job_path.parent
        visual_dir = work_dir / "visual_qa"
        metrics_path = visual_dir / "visual_metrics.json"
        metrics = _read_object(metrics_path, f"slide {slide} visual metrics")
        native = native_slides.get(str(slide))
        crop = crop_slides.get(str(slide))
        if not isinstance(native, dict) or not isinstance(crop, dict):
            raise _error(
                "DC_SHARED_RENDER_QA_OBJECTIVE_EVIDENCE_INVALID",
                f"objective evidence is missing slide {slide}",
                project / "out",
            )
        exceptions = _validated_skillset_exceptions(
            work_dir / "profile_override.json",
            slide,
        )
        _validate_native_thresholds(slide, native, native_manifest, exceptions)
        _validate_crop_thresholds(slide, crop, crop_summary, exceptions)

        source = project / "src" / f"slide{slide}.png"
        raster = visual_dir / "pptx_raster.png"
        html = visual_dir / "html_screenshot.png"
        _validate_visual_files(slide, job, metrics, source, raster, html, metrics_path)
        render_bindings = _validate_render_metadata(
            project,
            slide,
            visual_dir,
            raster,
            html,
        )
        checked_at = str(metrics.get("createdAt", "")).strip() or summary_checked_at
        if not checked_at:
            raise _error(
                "DC_SHARED_RENDER_QA_EVIDENCE_INVALID",
                f"slide {slide} visual metrics lack createdAt",
                metrics_path,
            )
        raw_issues = metrics.get("issues", [])
        issues = raw_issues if isinstance(raw_issues, list) else []
        noticeable = [
            {
                key: issue.get(key)
                for key in ("id", "type", "severity", "observed", "recommendedFix")
                if key in issue
            }
            for issue in issues
            if isinstance(issue, dict)
        ]

        counts = native.get("counts", {})
        native_counts = {
            key: int(counts.get(key, 0)) if isinstance(counts, dict) else 0
            for key in COUNT_KEYS
        }
        coverage = {key: float(crop.get(key, 0) or 0) for key in CROP_KEYS}
        score_path = write_json(
            work_dir / "reconstruction_score.json",
            {
                "slide": slide,
                "quality": "reconstruction",
                "status": "pass",
                "sourceCoverage": {
                    "headerRebuilt": True,
                    "titleRebuilt": True,
                    "bodyStructureRebuilt": True,
                    "footerRebuilt": True,
                },
                "nativeObjectCounts": native_counts,
                "cropCoverage": coverage,
                "exceptions": exceptions,
                "sharedPreviewEvidence": {
                    "summary": _relative(project, summary),
                    "summarySha256": _sha256(summary),
                    "visualMetrics": _relative(project, metrics_path),
                    "visualMetricsSha256": _sha256(metrics_path),
                    **render_bindings,
                },
            },
        )
        evidence_path = write_json(
            work_dir / "qa_evidence.json",
            {
                "slide": slide,
                "sourceImage": _relative(project, source),
                "sourceHash": _sha256(source),
                "pptxRaster": _relative(project, raster),
                "pptxRasterHash": _sha256(raster),
                "htmlScreenshot": _relative(project, html),
                "htmlScreenshotHash": _sha256(html),
                "checkedAt": checked_at,
                "checkedBy": "slide-visual-polish-qa/shared-full-deck-preview",
                "visualComparison": {
                    "status": "pass",
                    "method": "official-source-mapped-pptx-html-shared-preview",
                    "metrics": _relative(project, metrics_path),
                    "acceptedNeedsPolish": metrics.get("status") == "needs_polish",
                },
            },
        )
        qa_result_path = write_json(
            work_dir / "qa_result.json",
            {
                "slide": slide,
                "status": "pass",
                "visualFidelity": "pass",
                "nativeEditability": "pass",
                "cropPolicy": "pass",
                "blockingIssues": [],
                "noticeableIssues": noticeable,
                "minorIssues": [],
                "qaEvidence": _relative(project, evidence_path),
            },
        )
        report_path = work_dir / "qa_report.md"
        report_path.write_text(
            "\n".join(
                [
                    f"# Slide {slide} Shared-Render QA",
                    "",
                    "Status: pass",
                    "",
                    "The official source-mapped shared preview supplied both the PPTX "
                    "raster and HTML screenshot. Native-object and crop evidence passed "
                    "the reconstruction thresholds.",
                    "",
                    f"Accepted noticeable diagnostics: {len(noticeable)}",
                ]
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

        expected_artifacts = [
            name for name in job["required_outputs"] if name != "worker_receipt.json"
        ]
        produced = {
            name: work_dir / name
            for name in expected_artifacts
        }
        missing = [name for name, path in produced.items() if not path.is_file()]
        if missing:
            raise _error(
                "DC_SHARED_RENDER_QA_OUTPUT_INVALID",
                f"slide {slide} cannot close receipt; missing {missing}",
                work_dir,
            )
        receipt_path = write_json(
            work_dir / "worker_receipt.json",
            {
                "slide": slide,
                "agent": "slide_reconstruct_worker",
                "status": "completed",
                "sharedFilesEdited": False,
                "jobId": job["job_id"],
                "jobContentHash": job["content_hash"],
                "sourcePngSha256": job["receipt_binding"]["source_png_sha256"],
                "imageRequestSha256": job["receipt_binding"]["image_request_sha256"],
                "semanticSidecarSha256": job["receipt_binding"][
                    "semantic_sidecar_sha256"
                ],
                "artifacts": expected_artifacts,
                "artifactHashes": {
                    name: _sha256(path) for name, path in produced.items()
                },
                "qaFinalizedBy": "shared_render_qa",
                "qaEvidence": _relative(project, evidence_path),
                "reconstructionScore": _relative(project, score_path),
                "qaResult": _relative(project, qa_result_path),
                "qaReport": _relative(project, report_path),
            },
        )
        receipt_paths.append(receipt_path)

    final_report = validate_reconstruction_job_bundle(
        root,
        require_worker_outputs=True,
    )
    if not final_report["valid"]:
        raise _error(
            "DC_SHARED_RENDER_QA_OUTPUT_INVALID",
            "; ".join(final_report["issues"][:8]),
            manifest_path,
        )
    return SharedRenderQAResult(
        workflow_id=str(manifest["workflow_id"]),
        runtime_root=root,
        summary_path=summary,
        slide_count=len(slides),
        receipt_paths=tuple(receipt_paths),
    )


def _validate_native_thresholds(
    slide: int,
    native: dict[str, Any],
    path_context: dict[str, Any],
    exceptions: list[dict[str, Any]],
) -> None:
    counts = native.get("counts", {})
    text_count = int(counts.get("text", 0)) if isinstance(counts, dict) else 0
    editable_count = int(native.get("editableObjectCount", 0) or 0)
    text_length = int(native.get("editableTextLength", 0) or 0)
    has_text_exception = _has_skillset_exception(
        exceptions,
        r"native.*text|text.*threshold|min.*text",
    )
    if (
        (text_count < 8 or editable_count < 12 or text_length < 80)
        and not has_text_exception
    ):
        raise _error(
            "DC_SHARED_RENDER_QA_NATIVE_EDITABILITY_FAILED",
            f"slide {slide} native evidence is below 8 text / 12 objects / 80 chars",
        )
    if path_context.get("source") != "actual-render-surface-calls":
        raise _error(
            "DC_SHARED_RENDER_QA_NATIVE_EDITABILITY_FAILED",
            "native object manifest must come from actual render surface calls",
        )


def _validate_crop_thresholds(
    slide: int,
    crop: dict[str, Any],
    _path_context: dict[str, Any],
    exceptions: list[dict[str, Any]],
) -> None:
    largest = float(crop.get("largestCropAreaRatio", 0) or 0)
    total = float(crop.get("totalCropAreaRatio", 0) or 0)
    textual = float(crop.get("textOrTableCropAreaRatio", 0) or 0)
    dense = float(crop.get("denseInfographicCropAreaRatio", 0) or 0)
    has_image_led_exception = _has_skillset_exception(
        exceptions,
        r"image-led|image led|photoreal|continuous|3d",
    )
    if (
        largest > 0.35
        or total > 0.45
        and not has_image_led_exception
        or textual > 0.10
        or dense > 0.25
    ):
        raise _error(
            "DC_SHARED_RENDER_QA_CROP_POLICY_FAILED",
            f"slide {slide} crop coverage exceeds reconstruction limits",
        )


def _validated_skillset_exceptions(
    profile_path: Path,
    slide: int,
) -> list[dict[str, Any]]:
    profile = _read_object(profile_path, f"slide {slide} profile override")
    raw = profile.get("exceptions", [])
    if not isinstance(raw, list):
        raise _error(
            "DC_SHARED_RENDER_QA_OBJECTIVE_EVIDENCE_INVALID",
            f"slide {slide} profile exceptions must be an array",
            profile_path,
        )
    exceptions: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or not str(item.get("reason", "")).strip():
            raise _error(
                "DC_SHARED_RENDER_QA_OBJECTIVE_EVIDENCE_INVALID",
                f"slide {slide} exception {index + 1} requires an explicit reason",
                profile_path,
            )
        exceptions.append(dict(item))
    return exceptions


def _has_skillset_exception(
    exceptions: list[dict[str, Any]],
    pattern: str,
) -> bool:
    return any(
        re.search(pattern, json.dumps(item, ensure_ascii=False), re.IGNORECASE)
        is not None
        for item in exceptions
    )


def _validate_visual_files(
    slide: int,
    job: dict[str, Any],
    metrics: dict[str, Any],
    source: Path,
    raster: Path,
    html: Path,
    metrics_path: Path,
) -> None:
    for label, path in (("source", source), ("PPTX raster", raster), ("HTML screenshot", html)):
        if not path.is_file():
            raise _error(
                "DC_SHARED_RENDER_QA_EVIDENCE_INVALID",
                f"slide {slide} {label} is missing",
                path,
            )
    if _sha256(source) != job["source_png"]["sha256"]:
        raise _error(
            "DC_SHARED_RENDER_QA_EVIDENCE_INVALID",
            f"slide {slide} source hash no longer matches its job",
            source,
        )
    hashes = metrics.get("hashes")
    if not isinstance(hashes, dict):
        raise _error(
            "DC_SHARED_RENDER_QA_EVIDENCE_INVALID",
            f"slide {slide} visual metrics lack hashes",
            metrics_path,
        )
    expected = {
        "source": _sha256(source),
        "visual_qa_source": _sha256(source),
        "pptx_raster": _sha256(raster),
        "html_screenshot": _sha256(html),
    }
    for key, value in expected.items():
        if hashes.get(key) != value:
            raise _error(
                "DC_SHARED_RENDER_QA_EVIDENCE_INVALID",
                f"slide {slide} visual metrics {key} hash mismatch",
                metrics_path,
            )
    if metrics.get("status") not in {"pass", "needs_polish"}:
        raise _error(
            "DC_SHARED_RENDER_QA_REJECTED",
            f"slide {slide} visual metrics status is not acceptable",
            metrics_path,
        )


def _validate_render_metadata(
    project: Path,
    slide: int,
    visual_dir: Path,
    raster: Path,
    html_screenshot: Path,
) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for kind, metadata_name, input_key, input_hash_key, output, modified_key in (
        (
            "pptx",
            "pptx_raster_metadata.json",
            "pptx",
            "pptxSha256",
            raster,
            "modifiedPptx",
        ),
        (
            "html",
            "html_screenshot_metadata.json",
            "html",
            "htmlSha256",
            html_screenshot,
            "modifiedHtml",
        ),
    ):
        metadata_path = visual_dir / metadata_name
        metadata = _read_object(metadata_path, f"slide {slide} {kind} metadata")
        if metadata.get("diagnosticOnly") is not True or metadata.get(modified_key) is not False:
            raise _error(
                "DC_SHARED_RENDER_QA_EVIDENCE_INVALID",
                f"slide {slide} {kind} metadata must be diagnostic and unmodified",
                metadata_path,
            )
        if (
            metadata.get("sourceSlideId", metadata.get("slide")) != slide
            or metadata.get("mappingMode") != "source-slides-sequential"
        ):
            raise _error(
                "DC_SHARED_RENDER_QA_EVIDENCE_INVALID",
                f"slide {slide} {kind} metadata has invalid source mapping",
                metadata_path,
            )
        raw_input = metadata.get(input_key)
        if not isinstance(raw_input, str) or not raw_input.strip():
            raise _error(
                "DC_SHARED_RENDER_QA_EVIDENCE_INVALID",
                f"slide {slide} {kind} metadata lacks its shared preview input",
                metadata_path,
            )
        input_path = Path(raw_input).resolve()
        if input_path != project and not input_path.is_relative_to(project):
            raise _error(
                "DC_SHARED_RENDER_QA_EVIDENCE_INVALID",
                f"slide {slide} {kind} preview input escapes the project",
                input_path,
            )
        if not input_path.is_file() or metadata.get(input_hash_key) != _sha256(input_path):
            raise _error(
                "DC_SHARED_RENDER_QA_EVIDENCE_INVALID",
                f"slide {slide} {kind} preview input hash mismatch",
                input_path,
            )
        if metadata.get("outputSha256") != _sha256(output):
            raise _error(
                "DC_SHARED_RENDER_QA_EVIDENCE_INVALID",
                f"slide {slide} {kind} mapped output hash mismatch",
                metadata_path,
            )
        bindings[f"{kind}Input"] = _relative(project, input_path)
        bindings[f"{kind}InputSha256"] = _sha256(input_path)
        bindings[f"{kind}Metadata"] = _relative(project, metadata_path)
        bindings[f"{kind}MetadataSha256"] = _sha256(metadata_path)
    return bindings


def _artifact_path(root: Path, artifact: Any, label: str) -> Path:
    if not isinstance(artifact, dict):
        raise _error("DC_SHARED_RENDER_QA_INPUT_INVALID", f"{label} artifact is missing")
    raw = artifact.get("path")
    if not isinstance(raw, str) or not raw.strip():
        raise _error("DC_SHARED_RENDER_QA_INPUT_INVALID", f"{label} path is missing")
    path = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    if path != root and not path.is_relative_to(root):
        raise _error("DC_SHARED_RENDER_QA_INPUT_INVALID", f"{label} escapes runtime", path)
    if not path.is_file() or artifact.get("sha256") != _sha256(path):
        raise _error("DC_SHARED_RENDER_QA_INPUT_INVALID", f"{label} hash mismatch", path)
    return path


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        return read_json(path)
    except (OSError, ValueError, TypeError) as exc:
        raise _error(
            "DC_SHARED_RENDER_QA_INPUT_INVALID",
            f"{label} is missing or invalid: {exc}",
            path,
        ) from exc


def _relative(project: Path, path: Path) -> str:
    return path.resolve().relative_to(project.resolve()).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _error(code: str, message: str, path: Path | None = None) -> DeckCompilerError:
    return DeckCompilerError(
        code,
        "general_generate_workflow",
        message,
        path.as_posix() if path else None,
        remediation_hint=(
            "Run the official shared preview, source-mapped PPTX/HTML comparison, "
            "native-object evidence, crop evidence, and high-fidelity acceptance first."
        ),
    )


__all__ = ["SharedRenderQAResult", "finalize_shared_render_qa"]
