"""Incremental ImageGen-to-reconstruction execution for fast high-fidelity decks."""

from __future__ import annotations

import hashlib
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..errors import DeckCompilerError
from ..identity import content_sha256
from ..manifest_io import read_json, write_json
from .image_requests import REQUEST_MANIFEST_NAME, validate_image_request_bundle
from .execution_profiles import resolve_execution_profile
from .reconstruction_jobs import (
    prepare_reconstruction_job,
    prepare_reconstruction_jobs,
)
from .vector_preflight import (
    prepare_vector_preflight,
    prepare_vector_preflight_slide,
)


STATE_NAME = "streaming_execution.json"
STATE_SCHEMA = "codex_streaming_image_reconstruction_execution"
STATE_VERSION = "1.0.0"
ACCEPTED_DIRECTORY = Path("image_batches") / "accepted"
QUALITY_HARDLOCKS = {
    "one_source_slide_per_fresh_context": True,
    "native_text_required": True,
    "native_structure_required": True,
    "full_slide_raster_forbidden": True,
    "measured_vector_preflight_required": True,
    "semantic_text_vectorization_forbidden": True,
    "source_mapped_per_slide_qa_required": True,
    "final_full_deck_gate_required": True,
}
_THREAD_LOCKS: dict[Path, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True, slots=True)
class StreamingExecutionPreparationResult:
    workflow_id: str
    runtime_root: Path
    state_path: Path
    slide_count: int


@dataclass(frozen=True, slots=True)
class StreamingImageAcceptanceResult:
    workflow_id: str
    runtime_root: Path
    slide_number: int
    acceptance_path: Path
    job_path: Path
    worker_prompt_path: Path


def prepare_streaming_execution(
    runtime_root: Path,
) -> StreamingExecutionPreparationResult:
    """Create the executable state plane before any ImageGen call is submitted."""

    root = runtime_root.resolve()
    request_path = root / "image_requests" / REQUEST_MANIFEST_NAME
    report = validate_image_request_bundle(root, request_path)
    if not report["valid"]:
        raise _error(
            "DC_STREAMING_INPUT_INVALID",
            "Image requests are invalid: " + "; ".join(report["issues"][:6]),
            request_path,
        )
    request = read_json(request_path)
    profile = _runtime_profile(root)
    rows = []
    for request_row in request["slides"]:
        slide = int(request_row["slide_number"])
        rows.append(
            {
                "slide_number": slide,
                "slide_id": request_row["slide_id"],
                "request_id": request_row["request_id"],
                "prompt": request_row["prompt"],
                "semantic_sidecar": request_row["semantic_sidecar"],
                "state": "IMAGE_PENDING",
                "image_call": None,
                "accepted_receipt": None,
                "reconstruction_job": None,
                "reconstruction_started_at": None,
                "authoring_completed_at": None,
            }
        )
    state = {
        "schema_name": STATE_SCHEMA,
        "schema_version": STATE_VERSION,
        "workflow_id": request["workflow_id"],
        "profile_name": profile.name,
        "slide_count": len(rows),
        "image_dispatch": {
            "platform_tool_id": "image_gen.imagegen",
            "strategy": "submit_all_independent_calls_then_accept_as_completed",
            "requested_parallelism": min(
                profile.max_imagegen_parallel_slides, len(rows)
            ),
            "one_call_per_slide": True,
        },
        "reconstruction_dispatch": {
            "strategy": "ready_queue",
            "max_parallel_workers": min(
                profile.max_reconstruction_workers, len(rows)
            ),
            "start_condition": "accepted_image_passed_inspection_and_vector_preflight",
            "batch_barrier_forbidden": True,
            "worker_model": profile.model,
            "worker_reasoning_effort": profile.reasoning_effort,
        },
        "render_and_qa": {
            "isolated_per_slide_builds": 0,
            "shared_full_deck_render_count": 2,
            "preview_purpose": "source_mapped_per_slide_pptx_and_html_qa",
            "final_purpose": "official_reconstruction_gate_and_openability",
            "quality_hardlocks": QUALITY_HARDLOCKS,
        },
        "slides": rows,
        "content_hash": "0" * 64,
    }
    _seal_state(state)
    state_path = write_json(root / STATE_NAME, state)
    return StreamingExecutionPreparationResult(
        workflow_id=request["workflow_id"],
        runtime_root=root,
        state_path=state_path,
        slide_count=len(rows),
    )


def accept_streaming_image(
    runtime_root: Path,
    *,
    slide_number: int,
    tool_call_id: str,
    queued_at: str,
    started_at: str,
    completed_at: str,
    pipeline_root: Path | None = None,
    python_executable: str | None = None,
    vector_backend: str = "easyocr",
    vector_deep: bool = True,
) -> StreamingImageAcceptanceResult:
    """Measure one result outside the state lock, then make its job ready."""

    root = runtime_root.resolve()
    with _state_lock(root):
        _validate_streaming_image_preflight_eligibility(root, slide_number)
    prepare_vector_preflight_slide(
        root,
        slide_number=slide_number,
        pipeline_root=pipeline_root,
        python_executable=python_executable,
        backend=vector_backend,
        deep=vector_deep,
    )
    with _state_lock(root):
        return _accept_streaming_image_locked(
            root,
            slide_number=slide_number,
            tool_call_id=tool_call_id,
            queued_at=queued_at,
            started_at=started_at,
            completed_at=completed_at,
        )


def _validate_streaming_image_preflight_eligibility(
    root: Path,
    slide_number: int,
) -> None:
    state_path = root / STATE_NAME
    state = _read_state(state_path)
    row = _slide_row(state, slide_number)
    if row["state"] != "IMAGE_PENDING":
        raise _error(
            "DC_STREAMING_STATE_INVALID",
            f"slide {slide_number} cannot be accepted from {row['state']}",
            state_path,
        )
    source = root / "pngtopptx-project" / "src" / f"slide{slide_number}.png"
    inspection = root / "inspections" / f"slide-{slide_number:03d}.json"
    try:
        inspection_payload = read_json(inspection)
    except (OSError, ValueError, TypeError) as exc:
        raise _error(
            "DC_STREAMING_IMAGE_REJECTED",
            f"slide {slide_number} inspection report is missing or invalid: {exc}",
            inspection,
        ) from exc
    if (
        str(inspection_payload.get("status", "")).upper() != "PASS"
        or inspection_payload.get("slide_number") != slide_number
    ):
        raise _error(
            "DC_STREAMING_IMAGE_REJECTED",
            f"slide {slide_number} must have a matching PASS inspection",
            inspection,
        )
    if not source.is_file():
        raise _error(
            "DC_STREAMING_IMAGE_REJECTED",
            f"slide {slide_number} source PNG is missing",
            source,
        )


def _accept_streaming_image_locked(
    runtime_root: Path,
    *,
    slide_number: int,
    tool_call_id: str,
    queued_at: str,
    started_at: str,
    completed_at: str,
) -> StreamingImageAcceptanceResult:
    """Accept one inspected PNG and immediately make its reconstruction job ready."""

    root = runtime_root.resolve()
    state_path = root / STATE_NAME
    state = _read_state(state_path)
    row = _slide_row(state, slide_number)
    if row["state"] != "IMAGE_PENDING":
        raise _error(
            "DC_STREAMING_STATE_INVALID",
            f"slide {slide_number} cannot be accepted from {row['state']}",
            state_path,
        )
    queued = _timestamp(queued_at, "queued_at")
    started = _timestamp(started_at, "started_at")
    completed = _timestamp(completed_at, "completed_at")
    if not queued <= started <= completed:
        raise _error(
            "DC_STREAMING_TIMING_INVALID",
            "ImageGen timestamps must satisfy queued_at <= started_at <= completed_at",
            state_path,
        )
    if not isinstance(tool_call_id, str) or not tool_call_id.strip():
        raise _error(
            "DC_STREAMING_INPUT_INVALID", "tool_call_id is required", state_path
        )

    source = root / "pngtopptx-project" / "src" / f"slide{slide_number}.png"
    inspection = root / "inspections" / f"slide-{slide_number:03d}.json"
    try:
        inspection_payload = read_json(inspection)
    except (OSError, ValueError, TypeError) as exc:
        raise _error(
            "DC_STREAMING_IMAGE_REJECTED",
            f"slide {slide_number} inspection report is missing or invalid: {exc}",
            inspection,
        ) from exc
    if (
        str(inspection_payload.get("status", "")).upper() != "PASS"
        or inspection_payload.get("slide_number") != slide_number
    ):
        raise _error(
            "DC_STREAMING_IMAGE_REJECTED",
            f"slide {slide_number} must have a matching PASS inspection",
            inspection,
        )
    if not source.is_file():
        raise _error(
            "DC_STREAMING_IMAGE_REJECTED",
            f"slide {slide_number} source PNG is missing",
            source,
        )
    prompt_path = _artifact_path(root, row["prompt"], "prompt")
    sidecar_path = _artifact_path(root, row["semantic_sidecar"], "semantic sidecar")
    call = {
        "slide_number": slide_number,
        "request_id": row["request_id"],
        "tool_call_id": tool_call_id.strip(),
        "prompt_sha256": _sha256(prompt_path),
        "selected_png_sha256": _sha256(source),
        "semantic_sidecar_sha256": _sha256(sidecar_path),
        "inspection_sha256": _sha256(inspection),
        "status": "ACCEPTED",
        "attempt_count": 1,
        "queued_at": _format_timestamp(queued),
        "started_at": _format_timestamp(started),
        "completed_at": _format_timestamp(completed),
        "duration_seconds": (completed - started).total_seconds(),
    }
    prepared = prepare_reconstruction_job(
        root,
        slide_number=slide_number,
        accepted_call=call,
    )
    acceptance = {
        "schema_name": "image_generation_acceptance_receipt",
        "schema_version": "1.0.0",
        "workflow_id": state["workflow_id"],
        **call,
        "source_png": _artifact(root, source),
        "inspection_report": _artifact(root, inspection),
        "reconstruction_job": _artifact(root, prepared.job_path),
        "worker_prompt": _artifact(root, prepared.worker_prompt_path),
        "content_hash": "0" * 64,
    }
    acceptance["content_hash"] = content_sha256(
        {key: value for key, value in acceptance.items() if key != "content_hash"}
    )
    acceptance_path = write_json(
        root / ACCEPTED_DIRECTORY / f"slide-{slide_number:03d}.json",
        acceptance,
    )
    row["state"] = "RECONSTRUCTION_READY"
    row["image_call"] = call
    row["accepted_receipt"] = _artifact(root, acceptance_path)
    row["reconstruction_job"] = _artifact(root, prepared.job_path)
    _seal_state(state)
    write_json(state_path, state)
    return StreamingImageAcceptanceResult(
        workflow_id=state["workflow_id"],
        runtime_root=root,
        slide_number=slide_number,
        acceptance_path=acceptance_path,
        job_path=prepared.job_path,
        worker_prompt_path=prepared.worker_prompt_path,
    )


def record_streaming_reconstruction(
    runtime_root: Path,
    *,
    slide_number: int,
    status: str,
    timestamp: str,
) -> Path:
    """Record a state transition under the same short cross-process lock."""

    root = runtime_root.resolve()
    with _state_lock(root):
        return _record_streaming_reconstruction_locked(
            root,
            slide_number=slide_number,
            status=status,
            timestamp=timestamp,
        )


def _record_streaming_reconstruction_locked(
    runtime_root: Path,
    *,
    slide_number: int,
    status: str,
    timestamp: str,
) -> Path:
    """Record ready-queue transitions without letting a partial job claim QA pass."""

    root = runtime_root.resolve()
    state_path = root / STATE_NAME
    state = _read_state(state_path)
    row = _slide_row(state, slide_number)
    moment = _timestamp(timestamp, "timestamp")
    normalized = status.strip().upper()
    if normalized == "STARTED":
        if row["state"] != "RECONSTRUCTION_READY":
            raise _error(
                "DC_STREAMING_STATE_INVALID",
                f"slide {slide_number} cannot start from {row['state']}",
                state_path,
            )
        image_completed = _timestamp(row["image_call"]["completed_at"], "completed_at")
        if moment < image_completed:
            raise _error(
                "DC_STREAMING_TIMING_INVALID",
                "reconstruction cannot start before the accepted image completes",
                state_path,
            )
        row["state"] = "RECONSTRUCTION_STARTED"
        row["reconstruction_started_at"] = _format_timestamp(moment)
    elif normalized == "AUTHORING_COMPLETED":
        if row["state"] != "RECONSTRUCTION_STARTED":
            raise _error(
                "DC_STREAMING_STATE_INVALID",
                f"slide {slide_number} cannot complete authoring from {row['state']}",
                state_path,
            )
        started = _timestamp(row["reconstruction_started_at"], "started_at")
        if moment < started:
            raise _error(
                "DC_STREAMING_TIMING_INVALID",
                "authoring completion cannot precede reconstruction start",
                state_path,
            )
        row["state"] = "AUTHORING_COMPLETED"
        row["authoring_completed_at"] = _format_timestamp(moment)
    else:
        raise _error(
            "DC_STREAMING_STATE_INVALID",
            "status must be STARTED or AUTHORING_COMPLETED",
            state_path,
        )
    _seal_state(state)
    return write_json(state_path, state)


def finalize_streaming_images(runtime_root: Path) -> dict[str, Path | int]:
    """Seal the batch under the state lock after every acceptance is durable."""

    root = runtime_root.resolve()
    with _state_lock(root):
        return _finalize_streaming_images_locked(root)


def _finalize_streaming_images_locked(
    runtime_root: Path,
) -> dict[str, Path | int]:
    """Seal all incremental receipts into the canonical complete batch manifest."""

    root = runtime_root.resolve()
    state_path = root / STATE_NAME
    state = _read_state(state_path)
    if any(row["image_call"] is None for row in state["slides"]):
        raise _error(
            "DC_STREAMING_INCOMPLETE",
            "all slides must have an accepted image before batch finalization",
            state_path,
        )
    calls = [dict(row["image_call"]) for row in state["slides"]]
    calls.sort(key=lambda row: int(row["slide_number"]))
    max_parallelism = _max_parallelism(calls)
    waves = []
    for wave_number, offset in enumerate(range(0, len(calls), 20), start=1):
        wave_calls = calls[offset : offset + 20]
        waves.append(
            {
                "wave_number": wave_number,
                "concurrent_dispatch": True,
                "slides": [int(call["slide_number"]) for call in wave_calls],
                "initial_call_count": len(wave_calls),
                "regeneration_call_count": 0,
                "accepted_count": len(wave_calls),
                "calls": wave_calls,
            }
        )
    batch = {
        "schema_name": "image_generation_batch_manifest",
        "schema_version": "1.0.0",
        "platform_tool_id": "image_gen.imagegen",
        "batch_size": 20,
        "dispatch_mode": "concurrent_wave",
        "acceptance_mode": "streaming_ready_queue",
        "call_strategy": "one_independent_builtin_call_per_slide",
        "slide_count": len(calls),
        "initial_call_count": len(calls),
        "regeneration_call_count": 0,
        "accepted_count": len(calls),
        "requested_parallelism": min(20, len(calls)),
        "max_observed_parallelism": max_parallelism,
        "waves": waves,
    }
    batch_path = write_json(
        root / "image_batches" / "image_generation_batch_manifest.json", batch
    )
    prepare_vector_preflight(root)
    prepared = prepare_reconstruction_jobs(root)
    state["image_batch_manifest"] = _artifact(root, batch_path)
    state["reconstruction_job_manifest"] = _artifact(root, prepared.manifest_path)
    _seal_state(state)
    write_json(state_path, state)
    return {
        "batch_manifest_path": batch_path,
        "reconstruction_manifest_path": prepared.manifest_path,
        "max_observed_parallelism": max_parallelism,
    }


def validate_streaming_execution(
    runtime_root: Path,
    *,
    require_complete: bool = False,
    require_authoring_complete: bool = False,
    require_overlap: bool = False,
) -> dict[str, Any]:
    """Validate state lineage, accepted artifacts, timing, and overlap evidence."""

    root = runtime_root.resolve()
    state_path = root / STATE_NAME
    issues: list[str] = []
    try:
        state = _read_state(state_path)
    except (DeckCompilerError, OSError, ValueError, TypeError) as exc:
        message = exc.message if isinstance(exc, DeckCompilerError) else str(exc)
        return {
            "valid": False,
            "accepted_count": 0,
            "reconstruction_started_count": 0,
            "authoring_completed_count": 0,
            "max_observed_reconstruction_parallelism": 0,
            "overlap_proven": False,
            "issues": [message],
        }
    request_path = root / "image_requests" / REQUEST_MANIFEST_NAME
    request_report = validate_image_request_bundle(root, request_path)
    if not request_report["valid"]:
        issues.extend(f"image request: {issue}" for issue in request_report["issues"])
    request = read_json(request_path) if request_path.is_file() else {"slides": []}
    request_by_slide = {
        int(row["slide_number"]): row for row in request.get("slides", [])
    }
    accepted_count = 0
    started_count = 0
    authoring_completed_count = 0
    completion_times: list[datetime] = []
    reconstruction_starts: list[datetime] = []
    reconstruction_intervals: list[tuple[datetime, datetime]] = []
    for row in state.get("slides", []):
        slide = row.get("slide_number")
        expected = request_by_slide.get(slide)
        if expected is None:
            issues.append(f"state slide {slide} is not in the request manifest")
            continue
        for key in ("slide_id", "request_id", "prompt", "semantic_sidecar"):
            if row.get(key) != expected.get(key):
                issues.append(f"state slide {slide} {key} lineage mismatch")
        if row.get("image_call") is None:
            if row.get("state") != "IMAGE_PENDING":
                issues.append(f"state slide {slide} has no image call but is {row.get('state')}")
            continue
        accepted_count += 1
        call = row["image_call"]
        try:
            completion_times.append(_timestamp(call["completed_at"], "completed_at"))
        except (DeckCompilerError, KeyError) as exc:
            issues.append(f"state slide {slide} completion timestamp invalid: {exc}")
        for artifact_key in ("accepted_receipt", "reconstruction_job"):
            try:
                _artifact_path(root, row.get(artifact_key), artifact_key)
            except DeckCompilerError as exc:
                issues.append(exc.message)
        if row.get("state") in {"RECONSTRUCTION_STARTED", "AUTHORING_COMPLETED"}:
            started_count += 1
            try:
                reconstruction_starts.append(
                    _timestamp(row["reconstruction_started_at"], "started_at")
                )
            except (DeckCompilerError, KeyError, TypeError) as exc:
                issues.append(f"state slide {slide} reconstruction start invalid: {exc}")
        if row.get("state") == "AUTHORING_COMPLETED" and not row.get(
            "authoring_completed_at"
        ):
            issues.append(f"state slide {slide} lacks authoring_completed_at")
        elif row.get("state") == "AUTHORING_COMPLETED":
            try:
                start = _timestamp(row["reconstruction_started_at"], "started_at")
                end = _timestamp(row["authoring_completed_at"], "completed_at")
                if end < start:
                    issues.append(f"state slide {slide} authoring interval is reversed")
                else:
                    authoring_completed_count += 1
                    reconstruction_intervals.append((start, end))
            except (DeckCompilerError, KeyError, TypeError) as exc:
                issues.append(f"state slide {slide} authoring interval invalid: {exc}")

    overlap = bool(
        reconstruction_starts
        and completion_times
        and min(reconstruction_starts) < max(completion_times)
    )
    if require_complete and accepted_count != state.get("slide_count"):
        issues.append("streaming execution is not image-complete")
    if (
        require_authoring_complete
        and authoring_completed_count != state.get("slide_count")
    ):
        issues.append("streaming execution is not authoring-complete")
    if require_overlap and not overlap:
        issues.append("no reconstruction start overlaps unfinished ImageGen calls")
    reconstruction_parallelism = _max_interval_parallelism(reconstruction_intervals)
    configured_workers = state.get("reconstruction_dispatch", {}).get(
        "max_parallel_workers"
    )
    if (
        isinstance(configured_workers, int)
        and reconstruction_parallelism > configured_workers
    ):
        issues.append(
            "observed reconstruction parallelism exceeds the configured worker limit"
        )
    return {
        "valid": not issues,
        "workflow_id": state.get("workflow_id"),
        "slide_count": state.get("slide_count"),
        "accepted_count": accepted_count,
        "reconstruction_started_count": started_count,
        "authoring_completed_count": authoring_completed_count,
        "max_observed_reconstruction_parallelism": reconstruction_parallelism,
        "overlap_proven": overlap,
        "issues": issues,
    }


def simulate_fast_quality_schedule(
    *,
    image_seconds: Iterable[float],
    reconstruction_seconds: float,
    reconstruction_workers: int,
    shared_preview_and_final_qa_seconds: float,
    execution_profile: str = "sol-medium",
) -> dict[str, Any]:
    """Compute a deterministic critical-path budget; this is not a timing claim."""

    profile = resolve_execution_profile(execution_profile)
    durations = [float(value) for value in image_seconds]
    if not durations or any(value <= 0 for value in durations):
        raise ValueError("image_seconds must contain positive durations")
    if reconstruction_seconds <= 0 or shared_preview_and_final_qa_seconds <= 0:
        raise ValueError("reconstruction and QA durations must be positive")
    if reconstruction_workers <= 0:
        raise ValueError("reconstruction_workers must be positive")
    available = [0.0] * reconstruction_workers
    jobs: list[dict[str, float | int]] = []
    for slide, image_done in sorted(
        enumerate(durations, start=1), key=lambda item: (item[1], item[0])
    ):
        worker = min(range(reconstruction_workers), key=lambda index: available[index])
        started = max(image_done, available[worker])
        completed = started + reconstruction_seconds
        available[worker] = completed
        jobs.append(
            {
                "slide_number": slide,
                "worker": worker + 1,
                "image_completed_seconds": image_done,
                "reconstruction_started_seconds": started,
                "reconstruction_completed_seconds": completed,
            }
        )
    authoring_done = max(available)
    total = authoring_done + shared_preview_and_final_qa_seconds
    overlap = any(
        float(row["reconstruction_started_seconds"]) < max(durations) for row in jobs
    )
    return {
        "profile_name": profile.name,
        "slide_count": len(durations),
        "image_parallelism": len(durations),
        "reconstruction_workers": reconstruction_workers,
        "full_deck_render_count": 2,
        "image_generation_critical_path_seconds": max(durations),
        "authoring_critical_path_seconds": authoring_done,
        "shared_preview_and_final_qa_seconds": shared_preview_and_final_qa_seconds,
        "total_seconds": total,
        "target_seconds": 1800,
        "target_met": total <= 1800,
        "reconstruction_overlapped_image_generation": overlap,
        "quality_hardlocks": dict(QUALITY_HARDLOCKS),
        "jobs": jobs,
    }


def _runtime_profile(root: Path):
    plan_path = root / "skillset_execution_plan.json"
    plan = read_json(plan_path)
    row = plan.get("execution_profile")
    if not isinstance(row, dict):
        raise _error(
            "DC_STREAMING_PROFILE_INVALID",
            "skillset execution plan is missing execution_profile",
            plan_path,
        )
    profile = resolve_execution_profile(str(row.get("profile_name", "")))
    expected = {
        "target_model": profile.model,
        "target_reasoning_effort": profile.reasoning_effort,
        "max_imagegen_parallel_slides": profile.max_imagegen_parallel_slides,
        "max_reconstruction_workers": profile.max_reconstruction_workers,
    }
    for key, value in expected.items():
        if row.get(key) != value:
            raise _error(
                "DC_STREAMING_PROFILE_INVALID",
                f"execution_profile.{key} must be {value!r}",
                plan_path,
            )
    return profile


def _read_state(path: Path) -> dict[str, Any]:
    state = read_json(path)
    if state.get("schema_name") != STATE_SCHEMA or state.get("schema_version") != STATE_VERSION:
        raise _error("DC_STREAMING_STATE_INVALID", "streaming state schema is invalid", path)
    expected_hash = content_sha256(
        {key: value for key, value in state.items() if key != "content_hash"}
    )
    if state.get("content_hash") != expected_hash:
        raise _error("DC_STREAMING_STATE_INVALID", "streaming state content_hash mismatch", path)
    return state


def _seal_state(state: dict[str, Any]) -> None:
    state["content_hash"] = content_sha256(
        {key: value for key, value in state.items() if key != "content_hash"}
    )


def _slide_row(state: dict[str, Any], slide_number: int) -> dict[str, Any]:
    row = next(
        (
            candidate
            for candidate in state.get("slides", [])
            if candidate.get("slide_number") == slide_number
        ),
        None,
    )
    if row is None:
        raise _error(
            "DC_STREAMING_STATE_INVALID",
            f"streaming state has no slide {slide_number}",
        )
    return row


def _artifact(root: Path, path: Path) -> dict[str, str]:
    resolved = path.resolve()
    if not resolved.is_file() or (
        resolved != root and not resolved.is_relative_to(root)
    ):
        raise _error("DC_STREAMING_ARTIFACT_INVALID", f"artifact is invalid: {resolved}", resolved)
    return {"path": resolved.relative_to(root).as_posix(), "sha256": _sha256(resolved)}


def _artifact_path(root: Path, artifact: Any, label: str) -> Path:
    if not isinstance(artifact, dict):
        raise _error("DC_STREAMING_ARTIFACT_INVALID", f"{label} artifact is missing")
    raw = artifact.get("path")
    if not isinstance(raw, str) or not raw.strip():
        raise _error("DC_STREAMING_ARTIFACT_INVALID", f"{label} path is missing")
    path = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    if path != root and not path.is_relative_to(root):
        raise _error("DC_STREAMING_ARTIFACT_INVALID", f"{label} escapes the runtime", path)
    if not path.is_file() or artifact.get("sha256") != _sha256(path):
        raise _error("DC_STREAMING_ARTIFACT_INVALID", f"{label} hash or file mismatch", path)
    return path


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise _error("DC_STREAMING_TIMING_INVALID", f"{label} is required")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise _error("DC_STREAMING_TIMING_INVALID", f"{label} is not ISO-8601") from exc
    if parsed.tzinfo is None:
        raise _error("DC_STREAMING_TIMING_INVALID", f"{label} requires a timezone")
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _max_parallelism(calls: list[dict[str, Any]]) -> int:
    events: list[tuple[datetime, int]] = []
    for call in calls:
        events.append((_timestamp(call["started_at"], "started_at"), 1))
        events.append((_timestamp(call["completed_at"], "completed_at"), -1))
    active = 0
    maximum = 0
    for _, delta in sorted(events, key=lambda item: (item[0], item[1])):
        active += delta
        maximum = max(maximum, active)
    return maximum


def _max_interval_parallelism(
    intervals: list[tuple[datetime, datetime]],
) -> int:
    events: list[tuple[datetime, int]] = []
    for started, completed in intervals:
        events.append((started, 1))
        events.append((completed, -1))
    active = 0
    maximum = 0
    for _, delta in sorted(events, key=lambda item: (item[0], item[1])):
        active += delta
        maximum = max(maximum, active)
    return maximum


@contextmanager
def _state_lock(root: Path):
    """Serialize only state mutations across concurrent completion callbacks."""

    lock_path = (root / ".streaming_execution.lock").resolve()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _THREAD_LOCKS_GUARD:
        thread_lock = _THREAD_LOCKS.setdefault(lock_path, threading.RLock())
    with thread_lock:
        with lock_path.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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
            "Keep all ImageGen calls in flight, accept each inspected PNG once, and "
            "start its isolated reconstruction job immediately from the ready queue."
        ),
    )


__all__ = [
    "QUALITY_HARDLOCKS",
    "STATE_NAME",
    "StreamingExecutionPreparationResult",
    "StreamingImageAcceptanceResult",
    "accept_streaming_image",
    "finalize_streaming_images",
    "prepare_streaming_execution",
    "record_streaming_reconstruction",
    "simulate_fast_quality_schedule",
    "validate_streaming_execution",
]
