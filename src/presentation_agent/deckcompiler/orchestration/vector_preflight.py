"""Measured PNG-to-SVG preflight for the canonical PNGtoPPTX SkillSet.

This stage reuses PPTXlocal/raw as a measurement engine, then conservatively
traces only bounded flat-art regions.  It does not render PPTX and it never
turns a complete slide or semantic text into SVG.
"""

from __future__ import annotations

import ast
import hashlib
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from ..errors import DeckCompilerError
from ..identity import content_sha256
from ..manifest_io import read_json, write_json
from ..schemas import REPO_ROOT, validator_for
from ..vectorization import trace_png_to_svg, validate_svg
from .image_requests import REQUEST_MANIFEST_NAME, validate_image_request_bundle
from .skillset_plan import validate_skillset_execution_plan


PROJECT_DIRECTORY = "pngtopptx-project"
MANIFEST_NAME = "vector_preflight_manifest.json"
MANIFEST_SCHEMA = "pngtosvg_vector_preflight"
MANIFEST_VERSION = "1.0.0"
SLIDE_MANIFEST_NAME = "slide_vector_preflight.json"
SLIDE_MANIFEST_SCHEMA = "pngtosvg_vector_preflight_slide"
SLIDE_MANIFEST_VERSION = "1.0.0"
POLICY_ID = "raw-measured-bounded-vector-v1"
MAX_VECTOR_REGION_AREA_RATIO = 0.35
DEFAULT_MAX_WORKERS = 2
PIPELINE_ENVIRONMENT_VARIABLE = "PPTXLOCAL_RAW_PNGTOSVG_ROOT"
PYTHON_ENVIRONMENT_VARIABLE = "PPTXLOCAL_RAW_PYTHON"
RAW_BATCH_ADAPTER = Path(__file__).with_name("raw_measure_batch.py").resolve()


@dataclass(frozen=True, slots=True)
class VectorPreflightPreparationResult:
    workflow_id: str
    runtime_root: Path
    manifest_path: Path
    slide_count: int
    passed_vector_count: int
    measured_region_count: int


@dataclass(frozen=True, slots=True)
class VectorSlidePreflightPreparationResult:
    workflow_id: str
    runtime_root: Path
    slide_number: int
    manifest_path: Path
    passed_vector_count: int
    measured_region_count: int


def resolve_raw_pipeline_root(explicit_root: Path | None = None) -> Path:
    """Resolve raw/pipeline without copying or forking the external engine."""

    candidates: list[Path] = []
    if explicit_root is not None:
        candidates.append(explicit_root)
    configured = os.environ.get(PIPELINE_ENVIRONMENT_VARIABLE)
    if configured:
        candidates.append(Path(configured))
    for ancestor in (REPO_ROOT, *REPO_ROOT.parents):
        candidates.extend((ancestor / "raw", ancestor / "raw" / "pipeline"))

    inspected: list[str] = []
    for candidate in candidates:
        normalized = _normalize_pipeline_root(candidate)
        inspected.append(normalized.as_posix())
        if (normalized / "scripts" / "detect_elements.py").is_file():
            return normalized
    raise _error(
        "DC_VECTOR_PREFLIGHT_PIPELINE_MISSING",
        "PPTXlocal/raw detector was not found. Checked: "
        + ", ".join(dict.fromkeys(inspected)),
    )


def slide_preflight_path(runtime_root: Path, slide_number: int) -> Path:
    """Return the immutable per-slide preflight receipt path."""

    return (
        runtime_root.resolve()
        / PROJECT_DIRECTORY
        / "work"
        / f"slide{slide_number:02d}"
        / "vector_preflight"
        / SLIDE_MANIFEST_NAME
    )


def prepare_vector_preflight_slide(
    runtime_root: Path,
    *,
    slide_number: int,
    pipeline_root: Path | None = None,
    python_executable: str | None = None,
    backend: str = "easyocr",
    deep: bool = True,
) -> VectorSlidePreflightPreparationResult:
    """Measure and gate one accepted PNG without waiting for the image batch."""

    if backend not in {"easyocr", "tesseract"}:
        raise ValueError("backend must be easyocr or tesseract")
    if slide_number < 1:
        raise ValueError("slide_number must be positive")
    root = runtime_root.resolve()
    inputs = _load_request_context(root)
    request_row = next(
        (
            row
            for row in inputs["slides"]
            if int(row["slide_number"]) == slide_number
        ),
        None,
    )
    if request_row is None:
        raise _error(
            "DC_VECTOR_PREFLIGHT_INPUT_INVALID",
            f"image request manifest has no slide {slide_number}",
            inputs["request_path"],
        )
    source = root / PROJECT_DIRECTORY / "src" / f"slide{slide_number}.png"
    if not source.is_file():
        raise _error(
            "DC_VECTOR_PREFLIGHT_INPUT_INVALID",
            f"slide {slide_number} source PNG is missing",
            source,
        )
    existing = validate_vector_preflight_slide_bundle(root, slide_number)
    if existing["valid"]:
        payload = read_json(slide_preflight_path(root, slide_number))
        configured_pipeline = (
            _normalize_pipeline_root(pipeline_root).resolve()
            if pipeline_root is not None
            else None
        )
        configured_python = (
            _resolve_python_executable(python_executable)
            if python_executable is not None
            else None
        )
        if (
            (configured_pipeline is None or Path(payload["pipeline_provenance"]["root"]).resolve() == configured_pipeline)
            and (configured_python is None or payload["execution"]["python_executable"] == configured_python)
            and payload["execution"]["backend"] == backend
            and bool(payload["execution"]["deep_scan"]) == deep
        ):
            return VectorSlidePreflightPreparationResult(
                workflow_id=inputs["workflow_id"],
                runtime_root=root,
                slide_number=slide_number,
                manifest_path=slide_preflight_path(root, slide_number),
                passed_vector_count=existing["passed_vector_count"],
                measured_region_count=existing["measured_region_count"],
            )
    pipeline = resolve_raw_pipeline_root(pipeline_root)
    executable = _resolve_python_executable(
        python_executable
        or os.environ.get(PYTHON_ENVIRONMENT_VARIABLE)
        or sys.executable
    )
    project = root / PROJECT_DIRECTORY
    measured = _run_measurement_batches(
        root=root,
        project=project,
        pipeline=pipeline,
        rows=[request_row],
        executable=executable,
        backend=backend,
        deep=deep,
        max_workers=1,
    )[slide_number]
    record = _build_slide_record(
        root=root,
        source=source,
        inventory_path=measured["inventory_path"],
        inventory=read_json(measured["inventory_path"]),
        request_row=request_row,
        backend=backend,
        deep=deep,
        command=measured["command"],
        stdout=measured["stdout"],
        stderr=measured["stderr"],
        batch_job_path=measured["batch_job_path"],
    )
    manifest_path = _write_slide_preflight_receipt(
        root=root,
        inputs=inputs,
        pipeline=pipeline,
        executable=executable,
        backend=backend,
        deep=deep,
        record=record,
    )
    report = validate_vector_preflight_slide_bundle(root, slide_number)
    if not report["valid"]:
        raise _error(
            "DC_VECTOR_PREFLIGHT_INVALID",
            "; ".join(report["issues"][:8]),
            manifest_path,
        )
    return VectorSlidePreflightPreparationResult(
        workflow_id=inputs["workflow_id"],
        runtime_root=root,
        slide_number=slide_number,
        manifest_path=manifest_path,
        passed_vector_count=report["passed_vector_count"],
        measured_region_count=report["measured_region_count"],
    )


def validate_vector_preflight_slide_bundle(
    runtime_root: Path,
    slide_number: int,
) -> dict[str, Any]:
    """Validate one immutable measured slide receipt and every bounded SVG."""

    root = runtime_root.resolve()
    manifest_path = slide_preflight_path(root, slide_number)
    issues: list[str] = []
    try:
        inputs = _load_request_context(root)
        payload = read_json(manifest_path)
    except (DeckCompilerError, OSError, ValueError, TypeError) as exc:
        message = exc.message if isinstance(exc, DeckCompilerError) else str(exc)
        return {
            "valid": False,
            "workflow_id": None,
            "slide_number": slide_number,
            "passed_vector_count": 0,
            "measured_region_count": 0,
            "issues": [message],
        }
    if payload.get("schema_name") != SLIDE_MANIFEST_SCHEMA:
        issues.append("slide vector preflight schema_name mismatch")
    if payload.get("schema_version") != SLIDE_MANIFEST_VERSION:
        issues.append("slide vector preflight schema_version mismatch")
    if payload.get("workflow_id") != inputs["workflow_id"]:
        issues.append("slide vector preflight workflow_id mismatch")
    if payload.get("policy_id") != POLICY_ID or payload.get("status") != "READY":
        issues.append("slide vector preflight policy/status mismatch")
    if payload.get("content_hash") != _manifest_hash(payload):
        issues.append("slide vector preflight content_hash mismatch")
    source_artifacts = payload.get("source_artifacts", {})
    for key, expected_path in (
        ("image_request_manifest", inputs["request_path"]),
        ("skillset_execution_plan", inputs["plan_path"]),
    ):
        artifact = source_artifacts.get(key) if isinstance(source_artifacts, dict) else None
        _validate_internal_artifact(root, artifact, f"source_artifacts.{key}", issues, expected_path)
    provenance = payload.get("pipeline_provenance", {})
    for key in ("detector", "batch_adapter", "svg_icon_library"):
        artifact = provenance.get(key) if isinstance(provenance, dict) else None
        if artifact is None and key == "svg_icon_library":
            continue
        _validate_external_artifact(artifact, f"pipeline_provenance.{key}", issues)
    record = payload.get("slide")
    measured_count = 0
    vector_count = 0
    if not isinstance(record, dict):
        issues.append("slide vector preflight slide must be an object")
    else:
        expected_row = next(
            (
                row
                for row in inputs["slides"]
                if int(row["slide_number"]) == slide_number
            ),
            None,
        )
        if expected_row is None:
            issues.append(f"image requests have no slide {slide_number}")
        else:
            if record.get("slide_number") != slide_number:
                issues.append("slide vector preflight slide_number mismatch")
            if record.get("slide_id") != expected_row.get("slide_id"):
                issues.append("slide vector preflight slide_id mismatch")
            if record.get("request_id") != expected_row.get("request_id"):
                issues.append("slide vector preflight request_id mismatch")
        source = root / PROJECT_DIRECTORY / "src" / f"slide{slide_number}.png"
        _validate_internal_artifact(
            root,
            record.get("source_png"),
            f"slide {slide_number} source_png",
            issues,
            source,
        )
        inventory_path = _validate_internal_artifact(
            root,
            record.get("measurement_inventory"),
            f"slide {slide_number} measurement_inventory",
            issues,
        )
        _validate_internal_artifact(
            root,
            record.get("detector_record"),
            f"slide {slide_number} detector_record",
            issues,
        )
        inventory: dict[str, Any] = {}
        if inventory_path is not None:
            try:
                inventory = read_json(inventory_path)
            except (OSError, ValueError, TypeError) as exc:
                issues.append(f"slide {slide_number} inventory is invalid: {exc}")
        semantic_boxes = _semantic_boxes(inventory)
        width = int(record.get("source_png", {}).get("width", 0))
        height = int(record.get("source_png", {}).get("height", 0))
        regions = record.get("regions")
        if not isinstance(regions, list):
            issues.append("slide vector preflight regions must be an array")
            regions = []
        for region in regions:
            _validate_region(
                root,
                region,
                width,
                height,
                semantic_boxes,
                f"slide {slide_number}",
                issues,
            )
            measured_count += 1
            if isinstance(region, dict) and region.get("disposition") == "bounded_svg_asset":
                vector_count += 1
        expected_hash = content_sha256(
            {key: value for key, value in record.items() if key != "slide_content_hash"}
        )
        if record.get("slide_content_hash") != expected_hash:
            issues.append("slide vector preflight slide_content_hash mismatch")
    if payload.get("measured_region_count") != measured_count:
        issues.append("slide vector preflight measured_region_count mismatch")
    if payload.get("passed_vector_count") != vector_count:
        issues.append("slide vector preflight passed_vector_count mismatch")
    return {
        "valid": not issues,
        "workflow_id": inputs["workflow_id"],
        "slide_number": slide_number,
        "passed_vector_count": vector_count,
        "measured_region_count": measured_count,
        "issues": issues,
    }


def prepare_vector_preflight(
    runtime_root: Path,
    *,
    pipeline_root: Path | None = None,
    python_executable: str | None = None,
    backend: str = "easyocr",
    max_workers: int = DEFAULT_MAX_WORKERS,
    deep: bool = True,
) -> VectorPreflightPreparationResult:
    """Measure all selected PNGs once and trace safe, bounded flat regions."""

    if backend not in {"easyocr", "tesseract"}:
        raise ValueError("backend must be easyocr or tesseract")
    if not 1 <= max_workers <= 4:
        raise ValueError("max_workers must be between 1 and 4")
    root = runtime_root.resolve()
    inputs = _load_inputs(root)
    pipeline: Path
    if pipeline_root is None and not os.environ.get(PIPELINE_ENVIRONMENT_VARIABLE):
        first_slide = int(inputs["slides"][0]["slide_number"])
        first_report = validate_vector_preflight_slide_bundle(root, first_slide)
        if first_report["valid"]:
            first_receipt = read_json(slide_preflight_path(root, first_slide))
            pipeline = Path(first_receipt["pipeline_provenance"]["root"]).resolve()
        else:
            pipeline = resolve_raw_pipeline_root(None)
    else:
        pipeline = resolve_raw_pipeline_root(pipeline_root)
    detector = (pipeline / "scripts" / "detect_elements.py").resolve()
    icon_library = (pipeline / "scripts" / "svg_icons.py").resolve()
    project = root / PROJECT_DIRECTORY
    executable = _resolve_python_executable(
        python_executable
        or os.environ.get(PYTHON_ENVIRONMENT_VARIABLE)
        or sys.executable
    )
    records: list[dict[str, Any]] = []
    receipts_reused = True
    for row in inputs["slides"]:
        slide = int(row["slide_number"])
        report = validate_vector_preflight_slide_bundle(root, slide)
        if not report["valid"]:
            receipts_reused = False
            records = []
            break
        receipt = read_json(slide_preflight_path(root, slide))
        if (
            Path(receipt["pipeline_provenance"]["root"]).resolve() != pipeline
            or receipt["execution"]["backend"] != backend
            or bool(receipt["execution"]["deep_scan"]) != deep
            or receipt["execution"]["python_executable"] != executable
        ):
            receipts_reused = False
            records = []
            break
        records.append(receipt["slide"])

    if not receipts_reused:
        measurements = _run_measurement_batches(
            root=root,
            project=project,
            pipeline=pipeline,
            rows=inputs["slides"],
            executable=executable,
            backend=backend,
            deep=deep,
            max_workers=max_workers,
        )

        def build(row: dict[str, Any]) -> dict[str, Any]:
            slide = int(row["slide_number"])
            measured = measurements[slide]
            source = project / "src" / f"slide{slide}.png"
            inventory_path = measured["inventory_path"]
            record = _build_slide_record(
                root=root,
                source=source,
                inventory_path=inventory_path,
                inventory=read_json(inventory_path),
                request_row=row,
                backend=backend,
                deep=deep,
                command=measured["command"],
                stdout=measured["stdout"],
                stderr=measured["stderr"],
                batch_job_path=measured["batch_job_path"],
            )
            _write_slide_preflight_receipt(
                root=root,
                inputs=inputs,
                pipeline=pipeline,
                executable=executable,
                backend=backend,
                deep=deep,
                record=record,
            )
            return record

        with ThreadPoolExecutor(
            max_workers=min(max_workers, len(inputs["slides"]))
        ) as pool:
            futures = {pool.submit(build, row): row for row in inputs["slides"]}
            for future in as_completed(futures):
                records.append(future.result())
    records.sort(key=lambda row: row["slide_number"])

    payload: dict[str, Any] = {
        "schema_name": MANIFEST_SCHEMA,
        "schema_version": MANIFEST_VERSION,
        "workflow_id": inputs["workflow_id"],
        "policy_id": POLICY_ID,
        "status": "READY",
        "engine_role": "measurement_and_bounded_vector_preflight_only",
        "canonical_renderer": "slide-image-dual-render",
        "pipeline_provenance": {
            "root": pipeline.as_posix(),
            "detector": _external_artifact(detector),
            "batch_adapter": _external_artifact(RAW_BATCH_ADAPTER),
            "svg_icon_library": (
                _external_artifact(icon_library) if icon_library.is_file() else None
            ),
            "svg_icon_names": _svg_icon_names(icon_library),
            "reuse_mode": "external_measurement_engine_no_repo_local_fork",
        },
        "execution": {
            "backend": backend,
            "python_executable": executable,
            "canvas": "native",
            "deep_text": True,
            "deep_scan": deep,
            "max_parallel_measurement_workers": min(max_workers, len(records)),
            "ocr_reader_initializations_maximum": min(max_workers, len(records)),
            "measurement_dispatch": "bounded_batch_processes_shared_reader_per_worker",
            "additional_model_calls": 0,
        },
        "quality_contract": {
            "measured_coordinates_authoritative": True,
            "semantic_text_vectorization_forbidden": True,
            "full_slide_vectorization_forbidden": True,
            "full_slide_raster_delivery_forbidden": True,
            "maximum_vector_region_area_ratio": MAX_VECTOR_REGION_AREA_RATIO,
            "continuous_tone_vectorization_forbidden": True,
            "svg_security_and_fidelity_gate_required": True,
            "native_pptx_rebuild_remains_default": True,
        },
        "source_artifacts": {
            "image_request_manifest": _artifact(root, inputs["request_path"]),
            "image_generation_batch_manifest": _artifact(root, inputs["batch_path"]),
            "skillset_execution_plan": _artifact(root, inputs["plan_path"]),
        },
        "slide_count": len(records),
        "measured_region_count": sum(len(row["regions"]) for row in records),
        "passed_vector_count": sum(
            region["disposition"] == "bounded_svg_asset"
            for row in records
            for region in row["regions"]
        ),
        "slides": records,
        "content_hash": "0" * 64,
    }
    payload["content_hash"] = _manifest_hash(payload)
    manifest_path = write_json(project / "work" / MANIFEST_NAME, payload)
    report = validate_vector_preflight_bundle(root)
    if not report["valid"]:
        raise _error(
            "DC_VECTOR_PREFLIGHT_INVALID",
            "; ".join(report["issues"][:8]),
            manifest_path,
        )
    return VectorPreflightPreparationResult(
        workflow_id=inputs["workflow_id"],
        runtime_root=root,
        manifest_path=manifest_path,
        slide_count=len(records),
        passed_vector_count=payload["passed_vector_count"],
        measured_region_count=payload["measured_region_count"],
    )


def validate_vector_preflight_bundle(runtime_root: Path) -> dict[str, Any]:
    """Validate lineage, measurements, bounded assets, and forbidden SVG content."""

    root = runtime_root.resolve()
    manifest_path = root / PROJECT_DIRECTORY / "work" / MANIFEST_NAME
    issues: list[str] = []
    try:
        inputs = _load_inputs(root)
        payload = read_json(manifest_path)
    except (DeckCompilerError, OSError, ValueError, TypeError) as exc:
        message = exc.message if isinstance(exc, DeckCompilerError) else str(exc)
        return {"valid": False, "workflow_id": None, "slide_count": 0, "issues": [message]}

    for error in sorted(
        validator_for(MANIFEST_SCHEMA).iter_errors(payload),
        key=lambda item: list(item.absolute_path),
    ):
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        issues.append(f"schema {location}: {error.message}")
    if payload.get("workflow_id") != inputs["workflow_id"]:
        issues.append("vector preflight workflow_id mismatch")
    if payload.get("content_hash") != _manifest_hash(payload):
        issues.append("vector preflight content_hash mismatch")

    source_artifacts = payload.get("source_artifacts", {})
    for key, expected_path in (
        ("image_request_manifest", inputs["request_path"]),
        ("image_generation_batch_manifest", inputs["batch_path"]),
        ("skillset_execution_plan", inputs["plan_path"]),
    ):
        artifact = source_artifacts.get(key) if isinstance(source_artifacts, dict) else None
        _validate_internal_artifact(
            root,
            artifact,
            f"source_artifacts.{key}",
            issues,
            expected_path,
        )

    provenance = payload.get("pipeline_provenance", {})
    for key in ("detector", "batch_adapter", "svg_icon_library"):
        artifact = provenance.get(key) if isinstance(provenance, dict) else None
        if artifact is None and key == "svg_icon_library":
            continue
        _validate_external_artifact(artifact, f"pipeline_provenance.{key}", issues)
    if isinstance(provenance, dict):
        icon_artifact = provenance.get("svg_icon_library")
        icon_path = (
            Path(icon_artifact["path"])
            if isinstance(icon_artifact, dict) and isinstance(icon_artifact.get("path"), str)
            else None
        )
        expected_names = _svg_icon_names(icon_path) if icon_path is not None else []
        if provenance.get("svg_icon_names") != expected_names:
            issues.append("pipeline_provenance.svg_icon_names mismatch")

    expected_sources = {
        int(row["slide_number"]): root
        / PROJECT_DIRECTORY
        / "src"
        / f"slide{int(row['slide_number'])}.png"
        for row in inputs["slides"]
    }
    slides = payload.get("slides")
    if not isinstance(slides, list):
        slides = []
    if [row.get("slide_number") for row in slides if isinstance(row, dict)] != sorted(expected_sources):
        issues.append("vector preflight slides must cover every selected source slide in order")

    vector_count = 0
    measured_count = 0
    for row in slides:
        if not isinstance(row, dict):
            issues.append("vector preflight slide row must be an object")
            continue
        slide = row.get("slide_number")
        label = f"vector preflight slide {slide}"
        source = expected_sources.get(slide)
        if source is None:
            issues.append(f"{label} is unexpected")
            continue
        source_artifact = row.get("source_png")
        _validate_internal_artifact(root, source_artifact, label + " source_png", issues, source)
        inventory_path = _validate_internal_artifact(
            root, row.get("measurement_inventory"), label + " inventory", issues
        )
        _validate_internal_artifact(
            root, row.get("detector_record"), label + " detector_record", issues
        )
        _validate_internal_artifact(
            root,
            row.get("measurement_batch_job"),
            label + " measurement_batch_job",
            issues,
        )
        if inventory_path is None:
            continue
        try:
            inventory = read_json(inventory_path)
        except (OSError, ValueError, TypeError) as exc:
            issues.append(f"{label} inventory is invalid JSON: {exc}")
            continue
        canvas = inventory.get("canvas_px", {})
        try:
            width, height = _png_size(source)
        except (OSError, ValueError) as exc:
            issues.append(f"{label} source PNG is invalid: {exc}")
            continue
        if canvas != {"w": width, "h": height}:
            issues.append(f"{label} inventory must use native {width}x{height} canvas")
        semantic_boxes = _semantic_boxes(inventory)
        regions = row.get("regions") if isinstance(row.get("regions"), list) else []
        measured_count += len(regions)
        for region in regions:
            _validate_region(root, region, width, height, semantic_boxes, label, issues)
            if isinstance(region, dict) and region.get("disposition") == "bounded_svg_asset":
                vector_count += 1
        expected_slide_hash = content_sha256(
            {key: value for key, value in row.items() if key != "slide_content_hash"}
        )
        if row.get("slide_content_hash") != expected_slide_hash:
            issues.append(f"{label} slide_content_hash mismatch")

    if payload.get("measured_region_count") != measured_count:
        issues.append("vector preflight measured_region_count mismatch")
    if payload.get("passed_vector_count") != vector_count:
        issues.append("vector preflight passed_vector_count mismatch")
    return {
        "valid": not issues,
        "workflow_id": inputs["workflow_id"],
        "slide_count": len(slides),
        "passed_vector_count": vector_count,
        "measured_region_count": measured_count,
        "issues": issues,
    }


def _load_request_context(root: Path) -> dict[str, Any]:
    request_path = root / "image_requests" / REQUEST_MANIFEST_NAME
    request_report = validate_image_request_bundle(root, request_path)
    if not request_report["valid"]:
        raise _error(
            "DC_VECTOR_PREFLIGHT_INPUT_INVALID",
            "Image request lineage is invalid: " + "; ".join(request_report["issues"][:6]),
            request_path,
        )
    request = read_json(request_path)
    workflow_id = str(request.get("workflow_id", "")).strip()
    plan_path = root / "skillset_execution_plan.json"
    plan_issues = validate_skillset_execution_plan(plan_path, expected_workflow_id=workflow_id)
    if plan_issues:
        raise _error(
            "DC_VECTOR_PREFLIGHT_INPUT_INVALID",
            "skillset execution plan is invalid: " + "; ".join(plan_issues[:6]),
            plan_path,
        )
    return {
        "workflow_id": workflow_id,
        "slides": request["slides"],
        "request_path": request_path,
        "plan_path": plan_path,
    }


def _load_inputs(root: Path) -> dict[str, Any]:
    context = _load_request_context(root)
    batch_path = root / "image_batches" / "image_generation_batch_manifest.json"
    batch = read_json(batch_path)
    _validate_batch(root, batch, context["slides"])
    return {**context, "batch_path": batch_path}


def _write_slide_preflight_receipt(
    *,
    root: Path,
    inputs: dict[str, Any],
    pipeline: Path,
    executable: str,
    backend: str,
    deep: bool,
    record: dict[str, Any],
) -> Path:
    slide_number = int(record["slide_number"])
    detector = (pipeline / "scripts" / "detect_elements.py").resolve()
    icon_library = (pipeline / "scripts" / "svg_icons.py").resolve()
    payload: dict[str, Any] = {
        "schema_name": SLIDE_MANIFEST_SCHEMA,
        "schema_version": SLIDE_MANIFEST_VERSION,
        "workflow_id": inputs["workflow_id"],
        "policy_id": POLICY_ID,
        "status": "READY",
        "engine_role": "measurement_and_bounded_vector_preflight_only",
        "canonical_renderer": "slide-image-dual-render",
        "pipeline_provenance": {
            "root": pipeline.as_posix(),
            "detector": _external_artifact(detector),
            "batch_adapter": _external_artifact(RAW_BATCH_ADAPTER),
            "svg_icon_library": (
                _external_artifact(icon_library) if icon_library.is_file() else None
            ),
            "svg_icon_names": _svg_icon_names(icon_library),
            "reuse_mode": "external_measurement_engine_no_repo_local_fork",
        },
        "execution": {
            "backend": backend,
            "python_executable": executable,
            "canvas": "native",
            "deep_text": True,
            "deep_scan": deep,
            "additional_model_calls": 0,
        },
        "quality_contract": {
            "measured_coordinates_authoritative": True,
            "semantic_text_vectorization_forbidden": True,
            "full_slide_vectorization_forbidden": True,
            "full_slide_raster_delivery_forbidden": True,
            "maximum_vector_region_area_ratio": MAX_VECTOR_REGION_AREA_RATIO,
            "continuous_tone_vectorization_forbidden": True,
            "svg_security_and_fidelity_gate_required": True,
            "native_pptx_rebuild_remains_default": True,
        },
        "source_artifacts": {
            "image_request_manifest": _artifact(root, inputs["request_path"]),
            "skillset_execution_plan": _artifact(root, inputs["plan_path"]),
        },
        "slide_number": slide_number,
        "measured_region_count": len(record["regions"]),
        "passed_vector_count": sum(
            region.get("disposition") == "bounded_svg_asset"
            for region in record["regions"]
        ),
        "slide": record,
        "content_hash": "0" * 64,
    }
    payload["content_hash"] = _manifest_hash(payload)
    return write_json(slide_preflight_path(root, slide_number), payload)


def _validate_batch(
    root: Path,
    batch: dict[str, Any],
    slides: list[dict[str, Any]],
) -> None:
    if batch.get("schema_name") != "image_generation_batch_manifest":
        raise _error("DC_VECTOR_PREFLIGHT_INPUT_INVALID", "image batch schema_name is invalid")
    if batch.get("platform_tool_id") != "image_gen.imagegen":
        raise _error("DC_VECTOR_PREFLIGHT_INPUT_INVALID", "image generation must use image_gen.imagegen")
    expected = {int(row["slide_number"]): row for row in slides}
    accepted: dict[int, dict[str, Any]] = {}
    for wave in batch.get("waves", []):
        if not isinstance(wave, dict) or wave.get("concurrent_dispatch") is not True:
            raise _error("DC_VECTOR_PREFLIGHT_INPUT_INVALID", "image batch waves must be concurrent")
        for call in wave.get("calls", []):
            if isinstance(call, dict) and call.get("status") == "ACCEPTED":
                slide = call.get("slide_number")
                if not isinstance(slide, int) or slide in accepted:
                    raise _error("DC_VECTOR_PREFLIGHT_INPUT_INVALID", "duplicate or invalid accepted slide")
                accepted[slide] = call
    if sorted(accepted) != sorted(expected):
        raise _error("DC_VECTOR_PREFLIGHT_INPUT_INVALID", "accepted images must cover every requested slide")
    if batch.get("accepted_count") != len(expected) or batch.get("slide_count") != len(expected):
        raise _error("DC_VECTOR_PREFLIGHT_INPUT_INVALID", "image batch counts do not match requests")
    for slide, request in expected.items():
        call = accepted[slide]
        if call.get("request_id") != request.get("request_id"):
            raise _error("DC_VECTOR_PREFLIGHT_INPUT_INVALID", f"slide {slide} request_id mismatch")
        prompt = (root / request["prompt"]["path"]).resolve()
        source = root / PROJECT_DIRECTORY / "src" / f"slide{slide}.png"
        if call.get("prompt_sha256") != _sha256_file(prompt):
            raise _error(
                "DC_VECTOR_PREFLIGHT_INPUT_INVALID",
                f"slide {slide} prompt_sha256 mismatch",
            )
        if call.get("selected_png_sha256") != _sha256_file(source):
            raise _error(
                "DC_VECTOR_PREFLIGHT_INPUT_INVALID",
                f"slide {slide} selected_png_sha256 mismatch",
            )


def _run_measurement_batches(
    *,
    root: Path,
    project: Path,
    pipeline: Path,
    rows: list[dict[str, Any]],
    executable: str,
    backend: str,
    deep: bool,
    max_workers: int,
) -> dict[int, dict[str, Any]]:
    worker_count = min(max_workers, len(rows))
    chunks: list[list[dict[str, Any]]] = [[] for _ in range(worker_count)]
    for index, row in enumerate(rows):
        chunks[index % worker_count].append(row)
    batch_root = project / "work" / "vector_preflight_batches"
    batch_root.mkdir(parents=True, exist_ok=True)
    batch_specs: list[tuple[Path, list[dict[str, Any]], list[str]]] = []
    for index, chunk in enumerate(chunks, start=1):
        jobs = []
        for row in chunk:
            slide = int(row["slide_number"])
            inventory_path = (
                project
                / "work"
                / f"slide{slide:02d}"
                / "vector_preflight"
                / "measurement_inventory.json"
            )
            jobs.append(
                {
                    "slide_number": slide,
                    "source_png": (project / "src" / f"slide{slide}.png").as_posix(),
                    "inventory_path": inventory_path.as_posix(),
                }
            )
        batch_payload: dict[str, Any] = {
            "schema_name": "raw_pngtosvg_measurement_batch",
            "schema_version": "1.0.0",
            "jobs": jobs,
        }
        batch_payload["content_hash"] = content_sha256(batch_payload)
        slide_key = "-".join(
            f"{int(row['slide_number']):03d}" for row in chunk
        )
        batch_path = write_json(
            batch_root / f"batch-{index:02d}-slides-{slide_key}.json",
            batch_payload,
        )
        command = [
            executable,
            RAW_BATCH_ADAPTER.as_posix(),
            "--pipeline-root",
            pipeline.as_posix(),
            "--job-file",
            batch_path.as_posix(),
            "--backend",
            backend,
        ]
        if deep:
            command.append("--deep")
        batch_specs.append((batch_path, chunk, command))

    def execute(
        spec: tuple[Path, list[dict[str, Any]], list[str]],
    ) -> tuple[Path, list[dict[str, Any]], list[str], subprocess.CompletedProcess[str]]:
        batch_path, chunk, command = spec
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
        return batch_path, chunk, command, completed

    results: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = [pool.submit(execute, spec) for spec in batch_specs]
        for future in as_completed(futures):
            batch_path, chunk, command, completed = future.result()
            missing = []
            for row in chunk:
                slide = int(row["slide_number"])
                inventory = (
                    project
                    / "work"
                    / f"slide{slide:02d}"
                    / "vector_preflight"
                    / "measurement_inventory.json"
                )
                if not inventory.is_file():
                    missing.append(slide)
                results[slide] = {
                    "inventory_path": inventory,
                    "batch_job_path": batch_path,
                    "command": command,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            if completed.returncode != 0 or missing:
                detail = (completed.stderr or completed.stdout).strip()[-1600:]
                raise _error(
                    "DC_VECTOR_PREFLIGHT_MEASUREMENT_FAILED",
                    f"raw batch detector failed for slides "
                    f"{[int(row['slide_number']) for row in chunk]}: {detail}",
                    batch_path,
                )
    if sorted(results) != sorted(int(row["slide_number"]) for row in rows):
        raise _error(
            "DC_VECTOR_PREFLIGHT_MEASUREMENT_FAILED",
            "raw batch measurement did not cover every selected slide",
        )
    return results


def _build_slide_record(
    *,
    root: Path,
    source: Path,
    inventory_path: Path,
    inventory: dict[str, Any],
    request_row: dict[str, Any],
    backend: str,
    deep: bool,
    command: list[str],
    stdout: str,
    stderr: str,
    batch_job_path: Path,
) -> dict[str, Any]:
    slide = int(request_row["slide_number"])
    width, height = _png_size(source)
    if inventory.get("canvas_px") != {"w": width, "h": height}:
        raise _error(
            "DC_VECTOR_PREFLIGHT_MEASUREMENT_INVALID",
            f"slide {slide} detector did not preserve the native canvas",
            inventory_path,
        )
    notes = " ".join(str(value) for value in inventory.get("notes", [])).lower()
    if "pytesseract not installed" in notes or "text boxes unavailable" in notes:
        raise _error(
            "DC_VECTOR_PREFLIGHT_MEASUREMENT_INVALID",
            f"slide {slide} raw detector ran without its OCR dependency",
            inventory_path,
        )
    slide_dir = inventory_path.parent
    detector_record = {
        "schema_name": "raw_pngtosvg_detector_record",
        "schema_version": "1.0.0",
        "slide_number": slide,
        "backend": backend,
        "deep_scan": deep,
        "command": command,
        "exit_code": 0,
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
    }
    detector_record["content_hash"] = content_sha256(detector_record)
    detector_record_path = write_json(slide_dir / "detector_record.json", detector_record)
    semantic_boxes = _semantic_boxes(inventory)
    rows: list[dict[str, Any]] = []
    source_image = Image.open(source).convert("RGBA")
    for index, measured in enumerate(inventory.get("regions", []), start=1):
        if not isinstance(measured, dict):
            continue
        region_id = str(measured.get("id") or f"R{index:02d}")
        bbox = _validated_bbox(measured.get("bbox_px"), width, height, region_id)
        area_ratio = round((bbox["w"] * bbox["h"]) / (width * height), 8)
        overlap_ids = [
            box["id"] for box in semantic_boxes if _boxes_overlap(bbox, box["bbox_px"])
        ]
        row: dict[str, Any] = {
            "region_id": region_id,
            "kind_hint": str(measured.get("kind_hint", "unknown")),
            "bbox_px": bbox,
            "bbox_norm": measured.get("bbox_norm") or _norm_bbox(bbox, width, height),
            "area_ratio": area_ratio,
            "semantic_text_overlap_ids": overlap_ids,
            "measurement_confidence": measured.get("confidence"),
            "disposition": "native_rebuild_or_skill_review",
            "reason": "region_not_flat_vector_candidate",
        }
        if overlap_ids:
            row.update(
                disposition="native_rebuild_text_protected",
                reason="semantic_text_overlap_forbids_vectorization",
            )
        elif area_ratio > MAX_VECTOR_REGION_AREA_RATIO:
            row.update(
                disposition="native_rebuild_large_region",
                reason="region_exceeds_bounded_vector_area_limit",
            )
        elif row["kind_hint"] == "photo":
            row.update(
                disposition="bounded_raster_candidate",
                reason="continuous_tone_region_delegated_to_skill_crop_policy",
            )
        elif row["kind_hint"] in {"flat_shape", "line"}:
            candidate = slide_dir / "candidates" / f"{region_id}.png"
            svg = slide_dir / "vectors" / f"{region_id}.svg"
            report_path = slide_dir / "trace_reports" / f"{region_id}.json"
            candidate.parent.mkdir(parents=True, exist_ok=True)
            crop = source_image.crop(
                (bbox["x"], bbox["y"], bbox["x"] + bbox["w"], bbox["y"] + bbox["h"])
            )
            crop.save(candidate, format="PNG")
            try:
                report = trace_png_to_svg(
                    candidate,
                    svg,
                    region_area_ratio=area_ratio,
                    semantic_text_overlap=False,
                )
            except Exception as exc:  # region-level fail closed; native reconstruction remains available
                report = {
                    "schema_name": "pngtosvg_bounded_trace_report",
                    "schema_version": "1.0.0",
                    "status": "rejected",
                    "reason": f"trace_exception:{type(exc).__name__}",
                    "input_png": candidate.resolve().as_posix(),
                    "input_sha256": _sha256_file(candidate),
                    "fallback_required": True,
                    "fallback": "native_rebuild_or_skill_bounded_raster_review",
                }
            write_json(report_path, report)
            row["candidate_png"] = _artifact(root, candidate)
            row["trace_report"] = _artifact(root, report_path)
            if report.get("status") == "passed" and svg.is_file():
                preview = svg.with_suffix(".preview.png")
                row.update(
                    disposition="bounded_svg_asset",
                    reason="flat_region_passed_svg_security_and_fidelity_gates",
                    vector_svg=_artifact(root, svg),
                    vector_preview=_artifact(root, preview),
                )
            else:
                row.update(
                    disposition="native_rebuild_or_skill_review",
                    reason=str(report.get("reason") or "bounded_svg_gate_failed"),
                )
        rows.append(row)
    result: dict[str, Any] = {
        "slide_number": slide,
        "slide_id": request_row["slide_id"],
        "request_id": request_row["request_id"],
        "source_png": {**_artifact(root, source), "width": width, "height": height},
        "measurement_inventory": _artifact(root, inventory_path),
        "measurement_batch_job": _artifact(root, batch_job_path),
        "detector_record": _artifact(root, detector_record_path),
        "text_block_count": len(semantic_boxes),
        "regions": rows,
        "slide_content_hash": "0" * 64,
    }
    result["slide_content_hash"] = content_sha256(
        {key: value for key, value in result.items() if key != "slide_content_hash"}
    )
    return result


def _validate_region(
    root: Path,
    region: Any,
    width: int,
    height: int,
    semantic_boxes: list[dict[str, Any]],
    label: str,
    issues: list[str],
) -> None:
    if not isinstance(region, dict):
        issues.append(f"{label} region must be an object")
        return
    region_id = str(region.get("region_id", "<unknown>"))
    region_label = f"{label} region {region_id}"
    try:
        bbox = _validated_bbox(region.get("bbox_px"), width, height, region_id)
    except DeckCompilerError as exc:
        issues.append(exc.message)
        return
    expected_ratio = round((bbox["w"] * bbox["h"]) / (width * height), 8)
    if region.get("area_ratio") != expected_ratio:
        issues.append(f"{region_label} area_ratio mismatch")
    overlaps = sorted(
        box["id"] for box in semantic_boxes if _boxes_overlap(bbox, box["bbox_px"])
    )
    if sorted(region.get("semantic_text_overlap_ids", [])) != overlaps:
        issues.append(f"{region_label} semantic text overlap mismatch")
    disposition = region.get("disposition")
    if disposition != "bounded_svg_asset":
        return
    if overlaps:
        issues.append(f"{region_label} vectorizes semantic text")
    if expected_ratio > MAX_VECTOR_REGION_AREA_RATIO:
        issues.append(f"{region_label} exceeds bounded SVG area limit")
    if region.get("kind_hint") not in {"flat_shape", "line"}:
        issues.append(f"{region_label} is not a flat vector-safe kind")
    svg_path = _validate_internal_artifact(
        root, region.get("vector_svg"), region_label + " vector_svg", issues
    )
    candidate_path = _validate_internal_artifact(
        root, region.get("candidate_png"), region_label + " candidate_png", issues
    )
    report_path = _validate_internal_artifact(
        root, region.get("trace_report"), region_label + " trace_report", issues
    )
    preview_path = _validate_internal_artifact(
        root, region.get("vector_preview"), region_label + " vector_preview", issues
    )
    if svg_path is not None:
        gate = validate_svg(svg_path)
        if gate.get("status") != "passed":
            issues.append(f"{region_label} SVG security/portability gate failed")
        if gate.get("embedded_raster_count") or gate.get("text_element_count"):
            issues.append(f"{region_label} SVG contains raster or text elements")
    if report_path is not None:
        try:
            report = read_json(report_path)
        except (OSError, ValueError, TypeError) as exc:
            issues.append(f"{region_label} trace report is invalid JSON: {exc}")
        else:
            if report.get("status") != "passed":
                issues.append(f"{region_label} trace report did not pass")
            for key, path in (
                ("input_sha256", candidate_path),
                ("output_sha256", svg_path),
                ("preview_sha256", preview_path),
            ):
                if path is not None and report.get(key) != _sha256_file(path):
                    issues.append(f"{region_label} trace report {key} mismatch")
            fidelity = report.get("fidelity")
            if not isinstance(fidelity, dict):
                issues.append(f"{region_label} trace report fidelity is missing")
            else:
                try:
                    mae = float(fidelity.get("mean_absolute_error", 1))
                    difference = float(fidelity.get("pixel_difference_ratio", 1))
                except (TypeError, ValueError):
                    issues.append(f"{region_label} trace fidelity values are invalid")
                else:
                    if mae > 0.09 or difference > 0.18:
                        issues.append(
                            f"{region_label} trace fidelity exceeds the acceptance limit"
                        )


def _semantic_boxes(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for key in ("text_blocks", "suppressed_text"):
        for index, row in enumerate(inventory.get(key, []), start=1):
            if not isinstance(row, dict) or not isinstance(row.get("bbox_px"), dict):
                continue
            result.append(
                {
                    "id": str(row.get("id") or f"{key}-{index}"),
                    "bbox_px": row["bbox_px"],
                }
            )
    return result


def _validated_bbox(value: Any, width: int, height: int, label: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise _error("DC_VECTOR_PREFLIGHT_MEASUREMENT_INVALID", f"{label} bbox is missing")
    try:
        bbox = {key: int(value[key]) for key in ("x", "y", "w", "h")}
    except (KeyError, TypeError, ValueError) as exc:
        raise _error("DC_VECTOR_PREFLIGHT_MEASUREMENT_INVALID", f"{label} bbox is invalid") from exc
    if (
        bbox["x"] < 0
        or bbox["y"] < 0
        or bbox["w"] <= 0
        or bbox["h"] <= 0
        or bbox["x"] + bbox["w"] > width
        or bbox["y"] + bbox["h"] > height
    ):
        raise _error("DC_VECTOR_PREFLIGHT_MEASUREMENT_INVALID", f"{label} bbox escapes native canvas")
    return bbox


def _boxes_overlap(left: dict[str, int], right: dict[str, int]) -> bool:
    return (
        max(left["x"], right["x"]) < min(left["x"] + left["w"], right["x"] + right["w"])
        and max(left["y"], right["y"]) < min(left["y"] + left["h"], right["y"] + right["h"])
    )


def _norm_bbox(bbox: dict[str, int], width: int, height: int) -> dict[str, float]:
    return {
        "x": round(bbox["x"] / width, 6),
        "y": round(bbox["y"] / height, 6),
        "w": round(bbox["w"] / width, 6),
        "h": round(bbox["h"] / height, 6),
    }


def _normalize_pipeline_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if (root / "pipeline" / "scripts" / "detect_elements.py").is_file():
        return root / "pipeline"
    return root


def _svg_icon_names(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise _error(
            "DC_VECTOR_PREFLIGHT_PIPELINE_INVALID",
            f"raw SVG icon library cannot be inspected safely: {exc}",
            path,
        ) from exc
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "ICONS"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Dict):
            break
        names = [
            key.value
            for key in node.value.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        ]
        return sorted(names)
    raise _error(
        "DC_VECTOR_PREFLIGHT_PIPELINE_INVALID",
        "raw SVG icon library does not expose a literal ICONS mapping",
        path,
    )


def _resolve_python_executable(value: str) -> str:
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return candidate.resolve().as_posix()
    discovered = shutil.which(value)
    if discovered:
        return Path(discovered).resolve().as_posix()
    raise _error(
        "DC_VECTOR_PREFLIGHT_PYTHON_MISSING",
        f"raw measurement Python executable was not found: {value}",
    )


def _png_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        if image.format != "PNG":
            raise ValueError(f"not a PNG: {path}")
        width, height = image.size
    if width <= 0 or height <= 0 or abs((width / height) - (16 / 9)) > 0.02:
        raise ValueError(f"source PNG must be 16:9, got {width}x{height}")
    return width, height


def _artifact(root: Path, path: Path) -> dict[str, str]:
    resolved = path.resolve()
    if not resolved.is_file() or (resolved != root and not resolved.is_relative_to(root)):
        raise _error("DC_VECTOR_PREFLIGHT_ARTIFACT_INVALID", f"runtime artifact is invalid: {resolved}")
    return {"path": resolved.relative_to(root).as_posix(), "sha256": _sha256_file(resolved)}


def _external_artifact(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise _error("DC_VECTOR_PREFLIGHT_PIPELINE_MISSING", f"external pipeline artifact is missing: {resolved}")
    return {"path": resolved.as_posix(), "sha256": _sha256_file(resolved)}


def _validate_internal_artifact(
    root: Path,
    artifact: Any,
    label: str,
    issues: list[str],
    expected_path: Path | None = None,
) -> Path | None:
    if not isinstance(artifact, dict):
        issues.append(f"{label} artifact is missing")
        return None
    value = artifact.get("path")
    if not isinstance(value, str) or not value:
        issues.append(f"{label} path is missing")
        return None
    candidate = (root / value).resolve()
    if candidate != root and not candidate.is_relative_to(root):
        issues.append(f"{label} escapes runtime")
        return None
    if expected_path is not None and candidate != expected_path.resolve():
        issues.append(f"{label} path mismatch")
    if not candidate.is_file():
        issues.append(f"{label} file is missing")
        return None
    if artifact.get("sha256") != _sha256_file(candidate):
        issues.append(f"{label} sha256 mismatch")
    return candidate


def _validate_external_artifact(artifact: Any, label: str, issues: list[str]) -> None:
    if not isinstance(artifact, dict):
        issues.append(f"{label} artifact is missing")
        return
    value = artifact.get("path")
    if not isinstance(value, str) or not Path(value).is_absolute():
        issues.append(f"{label} must use an absolute external path")
        return
    path = Path(value).resolve()
    if not path.is_file():
        issues.append(f"{label} file is missing")
    elif artifact.get("sha256") != _sha256_file(path):
        issues.append(f"{label} sha256 mismatch")


def _manifest_hash(payload: dict[str, Any]) -> str:
    return content_sha256({key: value for key, value in payload.items() if key != "content_hash"})


def _sha256_file(path: Path) -> str:
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
            "Provide PPTXlocal/raw, rerun measured PNG-to-SVG preflight, then prepare "
            "the canonical slide-image-dual-render reconstruction jobs."
        ),
    )


__all__ = [
    "MANIFEST_NAME",
    "SLIDE_MANIFEST_NAME",
    "MAX_VECTOR_REGION_AREA_RATIO",
    "POLICY_ID",
    "VectorPreflightPreparationResult",
    "VectorSlidePreflightPreparationResult",
    "prepare_vector_preflight",
    "prepare_vector_preflight_slide",
    "resolve_raw_pipeline_root",
    "slide_preflight_path",
    "validate_vector_preflight_bundle",
    "validate_vector_preflight_slide_bundle",
]
