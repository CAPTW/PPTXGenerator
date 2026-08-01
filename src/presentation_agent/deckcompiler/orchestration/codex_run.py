"""Seal and validate live Codex ImageGen-to-PNGtoPPTX execution evidence."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from ..errors import DeckCompilerError
from ..identity import content_sha256
from ..manifest_io import read_json, write_json
from ..schemas import validator_for
from .image_requests import validate_image_request_bundle
from .skillset_plan import validate_skillset_execution_plan


SCHEMA_NAME = "codex_pptx_generation_run"
ARCHITECT_SKILL = "pptx-workflow-architect"
IMAGE_SKILL = "imagegen"
IMAGE_TOOL = "image_gen.imagegen"
RECONSTRUCTION_SKILL = "slide-editable-deck-orchestrator"
RENDERER_SKILL = "slide-image-dual-render"
VISUAL_QA_SKILL = "slide-visual-polish-qa"


def seal_codex_run_manifest(draft_path: Path, output_path: Path) -> dict[str, Any]:
    """Recompute referenced file hashes, seal content, and validate a run."""

    draft = draft_path.resolve()
    output = output_path.resolve()
    if not draft.is_file():
        raise _error(
            "DC_CODEX_RUN_DRAFT_MISSING", f"Codex run draft is missing: {draft}", draft
        )
    if draft == output:
        raise _error(
            "DC_CODEX_RUN_OUTPUT_CONFLICT",
            "Seal output must differ from the draft path.",
            output,
        )
    if draft.parent != output.parent:
        raise _error(
            "DC_CODEX_RUN_OUTPUT_LOCATION",
            "Seal output must share the draft directory so relative evidence paths remain stable.",
            output,
        )
    payload = read_json(draft)
    for label, artifact in _artifact_references(payload):
        path = _resolve_artifact(draft.parent, artifact.get("path"), label)
        artifact["sha256"] = _sha256_file(path)
    payload["content_hash"] = _content_hash(payload)
    report = validate_codex_run_manifest_payload(payload, manifest_path=draft)
    if not report["contract_valid"]:
        raise _error(
            "DC_CODEX_RUN_INVALID",
            "; ".join(report["issues"][:8]),
            draft,
        )
    write_json(output, payload)
    return payload


def validate_codex_run_manifest(
    path: Path,
    *,
    expected_workflow_id: str | None = None,
) -> dict[str, Any]:
    manifest_path = path.resolve()
    if not manifest_path.is_file():
        raise _error(
            "DC_CODEX_RUN_MISSING",
            f"Codex run manifest is missing: {manifest_path}",
            manifest_path,
        )
    payload = read_json(manifest_path)
    return validate_codex_run_manifest_payload(
        payload,
        manifest_path=manifest_path,
        expected_workflow_id=expected_workflow_id,
    )


def validate_codex_run_manifest_payload(
    payload: dict[str, Any],
    *,
    manifest_path: Path,
    expected_workflow_id: str | None = None,
) -> dict[str, Any]:
    """Validate schema, hashes, ordering, coverage, and completion gates."""

    issues: list[str] = []
    completion_issues: list[str] = []
    validator = validator_for(SCHEMA_NAME)
    for issue in sorted(
        validator.iter_errors(payload), key=lambda item: list(item.path)
    ):
        location = ".".join(str(part) for part in issue.path) or "$"
        issues.append(f"schema:{location}: {issue.message}")
    if issues:
        return _report(payload, issues, completion_issues)

    expected_content_hash = _content_hash(payload)
    if payload["content_hash"] != expected_content_hash:
        issues.append("content_hash does not match canonical manifest content")

    if (
        expected_workflow_id is not None
        and payload["workflow_id"] != expected_workflow_id
    ):
        issues.append(
            f"workflow_id mismatch: expected {expected_workflow_id}, got {payload['workflow_id']}"
        )

    base = manifest_path.resolve().parent
    resolved_artifacts: dict[str, Path] = {}
    for label, artifact in _artifact_references(payload):
        try:
            artifact_path = _resolve_artifact(base, artifact["path"], label)
        except DeckCompilerError as exc:
            issues.append(exc.message)
            continue
        resolved_artifacts[label] = artifact_path
        actual = _sha256_file(artifact_path)
        if actual != artifact["sha256"]:
            issues.append(f"{label} sha256 mismatch: {artifact_path}")

    architect = payload["architect"]
    image = payload["image_generation"]
    reconstruction = payload["reconstruction"]
    qa = payload["visual_qa"]
    delivery = payload["delivery"]
    slide_count = architect["slide_count"]
    ordered = [row["slide_number"] for row in image["slides"]]

    if image["requested_slide_count"] != slide_count:
        issues.append(
            "image requested_slide_count does not match architect slide_count"
        )
    if image["completed_slide_count"] != slide_count:
        issues.append(
            "image completed_slide_count does not match architect slide_count"
        )
    if len(image["slides"]) != slide_count:
        issues.append("image slide record count does not match architect slide_count")
    if ordered != list(range(1, slide_count + 1)):
        issues.append(
            f"image slide order must be contiguous 1..{slide_count}, got {ordered}"
        )
    if len({row["source_png"]["sha256"] for row in image["slides"]}) != slide_count:
        issues.append("selected source PNG hashes must be unique per slide")
    if qa["repair_iterations"] == 0:
        if reconstruction["execution_mode"] != "single_compile_fast_path":
            issues.append(
                "zero-repair run must use reconstruction.execution_mode "
                "single_compile_fast_path"
            )
    elif reconstruction["execution_mode"] != "post_repair_recompile":
        issues.append(
            "repaired run must use reconstruction.execution_mode post_repair_recompile"
        )

    issues.extend(
        _execution_artifact_issues(
            payload,
            resolved_artifacts,
        )
    )

    if reconstruction["output_pptx"]["sha256"] != delivery["pptx"]["sha256"]:
        issues.append("delivery PPTX is not hash-bound to reconstruction output")
    reconstruction_html = reconstruction["output_html"]
    delivery_html = delivery["html"]
    if (reconstruction_html is None) != (delivery_html is None):
        issues.append("delivery HTML presence does not match reconstruction output")
    elif reconstruction_html is not None and (
        reconstruction_html["sha256"] != delivery_html["sha256"]
    ):
        issues.append("delivery HTML is not hash-bound to reconstruction output")

    if payload["status"] == "COMPLETED":
        if qa["status"] != "PASS":
            completion_issues.append("completed run requires visual_qa.status PASS")
        if qa["fail_count"] != 0:
            completion_issues.append("completed run requires visual_qa.fail_count 0")
        if qa["blocking_count"] != 0:
            completion_issues.append(
                "completed run requires visual_qa.blocking_count 0"
            )
        if (
            reconstruction["quality_level"] == "strict"
            and qa["needs_polish_count"] != 0
        ):
            completion_issues.append(
                "strict completed run requires visual_qa.needs_polish_count 0"
            )
    else:
        if (
            qa["status"] == "PASS"
            and qa["fail_count"] == 0
            and qa["blocking_count"] == 0
        ):
            completion_issues.append(
                f"{payload['status']} contradicts zero-blocking PASS visual QA"
            )

    return _report(payload, issues, completion_issues)


def _artifact_references(
    payload: dict[str, Any],
) -> Iterator[tuple[str, dict[str, Any]]]:
    architect = payload.get("architect")
    if isinstance(architect, dict):
        for key in ("workflow_design", "blueprint", "design_system", "approval_record"):
            value = architect.get(key)
            if isinstance(value, dict):
                yield f"architect.{key}", value

    image = payload.get("image_generation")
    if isinstance(image, dict):
        request_manifest = image.get("request_manifest")
        if isinstance(request_manifest, dict):
            yield "image_generation.request_manifest", request_manifest
        batch_manifest = image.get("batch_manifest")
        if isinstance(batch_manifest, dict):
            yield "image_generation.batch_manifest", batch_manifest
        slides = image.get("slides")
        if isinstance(slides, list):
            for index, slide in enumerate(slides):
                if not isinstance(slide, dict):
                    continue
                for key in (
                    "prompt",
                    "source_png",
                    "semantic_sidecar",
                    "inspection_report",
                ):
                    value = slide.get(key)
                    if isinstance(value, dict):
                        yield f"image_generation.slides[{index}].{key}", value

    reconstruction = payload.get("reconstruction")
    if isinstance(reconstruction, dict):
        for key in (
            "execution_plan",
            "orchestration_state",
            "render_trace",
            "crop_plan",
            "crop_manifest",
            "crop_coverage_summary",
            "qa_evidence_summary",
            "output_pptx",
            "output_html",
            "native_object_manifest",
            "openability_report",
        ):
            value = reconstruction.get(key)
            if isinstance(value, dict):
                yield f"reconstruction.{key}", value

    visual_qa = payload.get("visual_qa")
    if isinstance(visual_qa, dict):
        for key in ("summary", "summary_markdown", "contact_sheet"):
            value = visual_qa.get(key)
            if isinstance(value, dict):
                yield f"visual_qa.{key}", value

    performance = payload.get("performance")
    if isinstance(performance, dict):
        timing_report = performance.get("timing_report")
        if isinstance(timing_report, dict):
            yield "performance.timing_report", timing_report

    delivery = payload.get("delivery")
    if isinstance(delivery, dict):
        for key in ("pptx", "html", "editability_inventory"):
            value = delivery.get(key)
            if isinstance(value, dict):
                yield f"delivery.{key}", value


def _resolve_artifact(base: Path, raw_path: Any, label: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise _error(
            "DC_CODEX_RUN_ARTIFACT_INVALID",
            f"{label} path must be a non-empty string",
            base,
        )
    candidate = Path(raw_path)
    unresolved = candidate if candidate.is_absolute() else base / candidate
    if unresolved.is_symlink():
        raise _error(
            "DC_CODEX_RUN_ARTIFACT_UNSAFE",
            f"{label} must not be a symlink: {unresolved}",
            unresolved,
        )
    resolved = unresolved.resolve()
    if not resolved.is_file():
        raise _error(
            "DC_CODEX_RUN_ARTIFACT_MISSING",
            f"{label} is missing: {resolved}",
            resolved,
        )
    return resolved


def _execution_artifact_issues(
    payload: dict[str, Any],
    artifacts: dict[str, Path],
) -> list[str]:
    """Reject placeholder bytes and cross-check the external Skill outputs."""

    issues: list[str] = []
    slide_count = payload["architect"]["slide_count"]

    for label, path in artifacts.items():
        if path.stat().st_size == 0:
            issues.append(f"{label} must not be empty: {path}")

    for key in ("workflow_design", "blueprint", "design_system", "approval_record"):
        _json_object(artifacts.get(f"architect.{key}"), f"architect.{key}", issues)

    request_manifest_path = artifacts.get("image_generation.request_manifest")
    request_manifest = _json_object(
        request_manifest_path,
        "image_generation.request_manifest",
        issues,
    )
    if request_manifest_path is not None:
        runtime_root = request_manifest_path.resolve().parent.parent
        request_report = validate_image_request_bundle(
            runtime_root,
            request_manifest_path,
        )
        issues.extend(
            f"image_generation.request_manifest: {issue}"
            for issue in request_report["issues"]
        )
        if request_manifest is not None:
            _validate_image_request_run_linkage(
                request_manifest,
                payload["image_generation"],
                artifacts,
                runtime_root,
                issues,
            )

    batch_manifest = _json_object(
        artifacts.get("image_generation.batch_manifest"),
        "image_generation.batch_manifest",
        issues,
    )
    if batch_manifest is not None:
        _validate_image_batch_manifest(
            batch_manifest,
            payload["image_generation"],
            slide_count,
            issues,
        )

    source_dimensions: list[tuple[int, int]] = []
    for index, slide in enumerate(payload["image_generation"]["slides"]):
        prefix = f"image_generation.slides[{index}]"
        prompt = _json_object(
            artifacts.get(f"{prefix}.prompt"), f"{prefix}.prompt", issues
        )
        sidecar = _json_object(
            artifacts.get(f"{prefix}.semantic_sidecar"),
            f"{prefix}.semantic_sidecar",
            issues,
        )
        inspection = _json_object(
            artifacts.get(f"{prefix}.inspection_report"),
            f"{prefix}.inspection_report",
            issues,
        )
        if prompt is not None and not prompt:
            issues.append(f"{prefix}.prompt must contain a real ImageGen request")
        if sidecar is not None and not sidecar:
            issues.append(f"{prefix}.semantic_sidecar must contain editable content")
        if (
            inspection is not None
            and str(inspection.get("status", "")).upper() != "PASS"
        ):
            issues.append(f"{prefix}.inspection_report must record status PASS")

        source_png = artifacts.get(f"{prefix}.source_png")
        dimensions = _png_dimensions(source_png, f"{prefix}.source_png", issues)
        if dimensions is not None:
            source_dimensions.append(dimensions)

        if slide["inspection_status"] != "PASS":
            issues.append(f"{prefix}.inspection_status must be PASS")

    if source_dimensions:
        if len(set(source_dimensions)) != 1:
            issues.append(
                f"selected source PNG dimensions must match, got {source_dimensions}"
            )
        for width, height in source_dimensions:
            if abs((width / height) - (16 / 9)) > 0.02:
                issues.append(f"selected source PNG must be 16:9, got {width}x{height}")

    timing_report = _json_object(
        artifacts.get("performance.timing_report"),
        "performance.timing_report",
        issues,
    )
    if timing_report is not None:
        _validate_timing_report(
            timing_report,
            payload["reconstruction"]["execution_mode"],
            slide_count,
            issues,
        )

    pptx_path = artifacts.get("reconstruction.output_pptx")
    _validate_pptx_package(pptx_path, slide_count, issues)
    _validate_no_source_slide_embedding(
        pptx_path,
        [
            artifacts.get(f"image_generation.slides[{index}].source_png")
            for index in range(slide_count)
        ],
        issues,
    )
    _validate_html(
        artifacts.get("reconstruction.output_html"),
        "reconstruction.output_html",
        issues,
    )

    native = _json_object(
        artifacts.get("reconstruction.native_object_manifest"),
        "reconstruction.native_object_manifest",
        issues,
    )
    if native is not None:
        _validate_native_manifest(native, slide_count, issues)

    execution_plan_path = artifacts.get("reconstruction.execution_plan")
    if execution_plan_path is not None:
        issues.extend(
            validate_skillset_execution_plan(
                execution_plan_path,
                expected_workflow_id=payload["workflow_id"],
            )
        )

    orchestration_state = _json_object(
        artifacts.get("reconstruction.orchestration_state"),
        "reconstruction.orchestration_state",
        issues,
    )
    if orchestration_state is not None:
        _validate_orchestration_state(
            orchestration_state,
            payload["reconstruction"]["quality_level"],
            slide_count,
            issues,
        )

    crop_plan = _json_object(
        artifacts.get("reconstruction.crop_plan"),
        "reconstruction.crop_plan",
        issues,
    )
    crop_manifest = _json_object(
        artifacts.get("reconstruction.crop_manifest"),
        "reconstruction.crop_manifest",
        issues,
    )
    crop_coverage = _json_object(
        artifacts.get("reconstruction.crop_coverage_summary"),
        "reconstruction.crop_coverage_summary",
        issues,
    )
    qa_evidence = _json_object(
        artifacts.get("reconstruction.qa_evidence_summary"),
        "reconstruction.qa_evidence_summary",
        issues,
    )
    if crop_plan is not None:
        _validate_crop_plan(crop_plan, issues)
    if crop_manifest is not None and not isinstance(crop_manifest, dict):
        issues.append("reconstruction.crop_manifest must be an object")
    if crop_coverage is not None:
        _validate_slide_keyed_evidence(
            crop_coverage,
            slide_count,
            "reconstruction.crop_coverage_summary",
            issues,
        )
    if qa_evidence is not None:
        _validate_qa_evidence(qa_evidence, slide_count, issues)

    render_trace = _json_object(
        artifacts.get("reconstruction.render_trace"),
        "reconstruction.render_trace",
        issues,
    )
    if render_trace is not None:
        _validate_render_trace(
            render_trace,
            payload["reconstruction"],
            artifacts,
            slide_count,
            issues,
        )

    openability = _json_object(
        artifacts.get("reconstruction.openability_report"),
        "reconstruction.openability_report",
        issues,
    )
    if openability is not None:
        _validate_openability_report(
            openability,
            payload["reconstruction"]["output_pptx"]["sha256"],
            issues,
        )

    qa_summary = _json_object(
        artifacts.get("visual_qa.summary"),
        "visual_qa.summary",
        issues,
    )
    if qa_summary is not None:
        _validate_qa_summary(
            qa_summary,
            payload["visual_qa"],
            slide_count,
            issues,
        )
    qa_summary_markdown = artifacts.get("visual_qa.summary_markdown")
    if qa_summary_markdown is not None:
        try:
            markdown_text = qa_summary_markdown.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            issues.append(f"visual_qa.summary_markdown must be UTF-8 text: {exc}")
        else:
            if "# Visual QA Summary" not in markdown_text:
                issues.append(
                    "visual_qa.summary_markdown must be the official Visual QA summary"
                )
    if payload["status"] == "COMPLETED" and qa_summary is not None:
        _validate_final_visual_qa_evidence(
            payload,
            artifacts,
            qa_summary,
            slide_count,
            issues,
        )
    _png_dimensions(
        artifacts.get("visual_qa.contact_sheet"),
        "visual_qa.contact_sheet",
        issues,
    )

    _validate_html(
        artifacts.get("delivery.html"),
        "delivery.html",
        issues,
    )
    return issues


def _json_object(
    path: Path | None,
    label: str,
    issues: list[str],
) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        issues.append(f"{label} must be valid UTF-8 JSON: {exc}")
        return None
    if not isinstance(value, dict):
        issues.append(f"{label} must contain a JSON object")
        return None
    return value


def _validate_image_request_run_linkage(
    manifest: dict[str, Any],
    image: dict[str, Any],
    artifacts: dict[str, Path],
    runtime_root: Path,
    issues: list[str],
) -> None:
    """Bind sealed run rows to the deterministic Architect-derived request rows."""

    request_rows = manifest.get("slides")
    image_rows = image.get("slides")
    if not isinstance(request_rows, list) or not isinstance(image_rows, list):
        return
    if len(request_rows) != len(image_rows):
        issues.append(
            "image_generation.request_manifest slide count does not match run slides"
        )
        return
    lineage_fields = (
        "slide_number",
        "slide_id",
        "request_id",
        "blueprint_entry_sha256",
        "visual_route_id",
        "visual_route_sha256",
        "layout_id",
        "layout_sha256",
        "evidence_refs",
    )
    for index, (request_row, image_row) in enumerate(zip(request_rows, image_rows)):
        label = f"image_generation.slides[{index}]"
        if not isinstance(request_row, dict) or not isinstance(image_row, dict):
            continue
        for field in lineage_fields:
            if image_row.get(field) != request_row.get(field):
                issues.append(
                    f"{label}.{field} does not match the Architect-derived request manifest"
                )
        for key in ("prompt", "semantic_sidecar"):
            manifest_artifact = request_row.get(key)
            run_artifact = image_row.get(key)
            actual_path = artifacts.get(f"{label}.{key}")
            if not isinstance(manifest_artifact, dict) or not isinstance(run_artifact, dict):
                continue
            manifest_path = _runtime_artifact_path(runtime_root, manifest_artifact.get("path"))
            if actual_path is None or manifest_path is None or actual_path.resolve() != manifest_path:
                issues.append(f"{label}.{key} path does not match request manifest")
            if run_artifact.get("sha256") != manifest_artifact.get("sha256"):
                issues.append(f"{label}.{key} sha256 does not match request manifest")


def _runtime_artifact_path(root: Path, raw: Any) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = Path(raw)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def _validate_image_batch_manifest(
    manifest: dict[str, Any],
    image: dict[str, Any],
    slide_count: int,
    issues: list[str],
) -> None:
    """Verify one concurrent built-in call per slide in deterministic waves of 20."""

    expected_values = {
        "schema_name": "image_generation_batch_manifest",
        "schema_version": "1.0.0",
        "platform_tool_id": IMAGE_TOOL,
        "batch_size": 20,
        "dispatch_mode": "concurrent_wave",
        "call_strategy": "one_independent_builtin_call_per_slide",
        "slide_count": slide_count,
    }
    for key, expected in expected_values.items():
        if manifest.get(key) != expected:
            issues.append(f"image_generation.batch_manifest.{key} must be {expected!r}")

    waves = manifest.get("waves")
    image_by_slide = {
        row["slide_number"]: row
        for row in image.get("slides", [])
        if isinstance(row, dict) and isinstance(row.get("slide_number"), int)
    }
    expected_wave_count = (slide_count + 19) // 20
    if not isinstance(waves, list) or len(waves) != expected_wave_count:
        issues.append(
            "image_generation.batch_manifest.waves must contain exactly "
            f"{expected_wave_count} wave(s)"
        )
        return

    attempts_by_slide: dict[int, int] = {}
    total_regenerations = 0
    for index, wave in enumerate(waves, start=1):
        label = f"image_generation.batch_manifest.waves[{index - 1}]"
        if not isinstance(wave, dict):
            issues.append(f"{label} must be an object")
            continue
        expected_slides = list(
            range((index - 1) * 20 + 1, min(index * 20, slide_count) + 1)
        )
        if wave.get("wave_number") != index:
            issues.append(f"{label}.wave_number must be {index}")
        if wave.get("concurrent_dispatch") is not True:
            issues.append(f"{label}.concurrent_dispatch must be true")
        if wave.get("slides") != expected_slides:
            issues.append(f"{label}.slides must be {expected_slides}")
        calls = wave.get("calls")
        if not isinstance(calls, list) or len(calls) != len(expected_slides):
            issues.append(
                f"{label}.calls must contain one call record per slide in the wave"
            )
            continue
        call_slides: list[int] = []
        wave_regenerations = 0
        for call_index, call in enumerate(calls):
            call_label = f"{label}.calls[{call_index}]"
            if not isinstance(call, dict):
                issues.append(f"{call_label} must be an object")
                continue
            slide_number = call.get("slide_number")
            attempt_count = call.get("attempt_count")
            call_slides.append(slide_number)
            if call.get("status") != "ACCEPTED":
                issues.append(f"{call_label}.status must be ACCEPTED")
            if not isinstance(attempt_count, int) or attempt_count not in (1, 2):
                issues.append(f"{call_label}.attempt_count must be 1 or 2")
                continue
            if isinstance(slide_number, int):
                attempts_by_slide[slide_number] = attempt_count
                image_row = image_by_slide.get(slide_number)
                if image_row is not None:
                    if call.get("request_id") != image_row.get("request_id"):
                        issues.append(
                            f"{call_label}.request_id must match the prepared request"
                        )
                    if call.get("prompt_sha256") != image_row.get("prompt", {}).get(
                        "sha256"
                    ):
                        issues.append(
                            f"{call_label}.prompt_sha256 must match the prepared prompt"
                        )
                    if call.get("selected_png_sha256") != image_row.get(
                        "source_png", {}
                    ).get("sha256"):
                        issues.append(
                            f"{call_label}.selected_png_sha256 must match the selected PNG"
                        )
            wave_regenerations += attempt_count - 1
        if call_slides != expected_slides:
            issues.append(f"{label}.calls must follow slide order {expected_slides}")
        if wave.get("initial_call_count") != len(expected_slides):
            issues.append(f"{label}.initial_call_count must equal its number of slides")
        if wave.get("regeneration_call_count") != wave_regenerations:
            issues.append(f"{label}.regeneration_call_count is inconsistent")
        if wave.get("accepted_count") != len(expected_slides):
            issues.append(f"{label}.accepted_count must equal its number of slides")
        total_regenerations += wave_regenerations

    if manifest.get("initial_call_count") != slide_count:
        issues.append(
            "image_generation.batch_manifest.initial_call_count must equal slide_count"
        )
    if manifest.get("regeneration_call_count") != total_regenerations:
        issues.append(
            "image_generation.batch_manifest.regeneration_call_count is inconsistent"
        )
    if manifest.get("accepted_count") != slide_count:
        issues.append(
            "image_generation.batch_manifest.accepted_count must equal slide_count"
        )
    for slide in image["slides"]:
        slide_number = slide["slide_number"]
        expected_regenerations = attempts_by_slide.get(slide_number, 1) - 1
        if slide["regeneration_count"] != expected_regenerations:
            issues.append(
                f"image slide {slide_number} regeneration_count does not match "
                "the batch manifest"
            )


def _validate_timing_report(
    report: dict[str, Any],
    execution_mode: str,
    slide_count: int,
    issues: list[str],
) -> None:
    """Validate measured timing without allowing a speed target to bypass quality."""

    expected_values = {
        "schema_name": "pptx_generation_execution_timing",
        "schema_version": "1.0.0",
        "profile_name": "fast-quality-20",
        "slide_count": slide_count,
        "target_seconds_20_slides": 1800,
        "quality_gates_take_precedence": True,
    }
    for key, expected in expected_values.items():
        if report.get(key) != expected:
            issues.append(f"performance.timing_report.{key} must be {expected!r}")

    for key in (
        "total_seconds",
        "image_generation_seconds",
        "reconstruction_seconds",
        "visual_qa_seconds",
    ):
        value = report.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            issues.append(f"performance.timing_report.{key} must be non-negative")
    total_seconds = report.get("total_seconds")
    if isinstance(total_seconds, (int, float)) and not isinstance(total_seconds, bool):
        if total_seconds <= 0:
            issues.append("performance.timing_report.total_seconds must be positive")

    timestamps: dict[str, datetime] = {}
    for key in ("started_at", "completed_at"):
        value = report.get(key)
        if not isinstance(value, str) or not value:
            issues.append(f"performance.timing_report.{key} must be an ISO timestamp")
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            issues.append(f"performance.timing_report.{key} must be an ISO timestamp")
            continue
        if parsed.tzinfo is None:
            issues.append(f"performance.timing_report.{key} must include a timezone")
            continue
        timestamps[key] = parsed
    if (
        "started_at" in timestamps
        and "completed_at" in timestamps
        and isinstance(total_seconds, (int, float))
    ):
        observed_seconds = (
            timestamps["completed_at"] - timestamps["started_at"]
        ).total_seconds()
        if observed_seconds <= 0 or abs(observed_seconds - total_seconds) > 1:
            issues.append(
                "performance.timing_report.total_seconds must match the timestamp span"
            )

    expected_compile_count = 1 if execution_mode == "single_compile_fast_path" else 2
    if report.get("full_deck_compile_count") != expected_compile_count:
        issues.append(
            "performance.timing_report.full_deck_compile_count must be "
            f"{expected_compile_count} for {execution_mode}"
        )

    target_applicable = slide_count == 20
    if report.get("target_applicable") is not target_applicable:
        issues.append(
            "performance.timing_report.target_applicable must reflect a 20-slide run"
        )
    expected_target_met: bool | None = None
    if target_applicable and isinstance(total_seconds, (int, float)):
        expected_target_met = total_seconds <= 1800
    if report.get("target_met") is not expected_target_met:
        issues.append("performance.timing_report.target_met is inconsistent")


def _png_dimensions(
    path: Path | None,
    label: str,
    issues: list[str],
) -> tuple[int, int] | None:
    if path is None:
        return None
    try:
        with path.open("rb") as stream:
            header = stream.read(24)
    except OSError as exc:
        issues.append(f"{label} could not be read as PNG: {exc}")
        return None
    if (
        len(header) < 24
        or header[:8] != b"\x89PNG\r\n\x1a\n"
        or header[12:16] != b"IHDR"
    ):
        issues.append(f"{label} is not a structurally valid PNG")
        return None
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    if width <= 0 or height <= 0:
        issues.append(f"{label} has invalid PNG dimensions {width}x{height}")
        return None
    return width, height


def _validate_pptx_package(
    path: Path | None,
    expected_slide_count: int,
    issues: list[str],
) -> None:
    if path is None:
        return
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            required = {
                "[Content_Types].xml",
                "_rels/.rels",
                "ppt/presentation.xml",
            }
            missing = sorted(required - names)
            if missing:
                issues.append(f"reconstruction.output_pptx is missing parts: {missing}")
            corrupt = archive.testzip()
            if corrupt is not None:
                issues.append(
                    f"reconstruction.output_pptx has a corrupt ZIP member: {corrupt}"
                )
            slides = sorted(
                name
                for name in names
                if re.fullmatch(r"ppt/slides/slide[1-9][0-9]*\.xml", name)
            )
    except (OSError, zipfile.BadZipFile) as exc:
        issues.append(f"reconstruction.output_pptx is not a valid PPTX package: {exc}")
        return
    if len(slides) != expected_slide_count:
        issues.append(
            "reconstruction.output_pptx slide count mismatch: "
            f"expected {expected_slide_count}, got {len(slides)}"
        )


def _validate_html(
    path: Path | None,
    label: str,
    issues: list[str],
) -> None:
    if path is None:
        return
    try:
        with path.open("rb") as stream:
            prefix = stream.read(1024 * 1024).decode("utf-8", errors="ignore").lower()
    except OSError as exc:
        issues.append(f"{label} could not be read: {exc}")
        return
    if "<html" not in prefix:
        issues.append(f"{label} does not contain an HTML document")


def _validate_native_manifest(
    manifest: dict[str, Any],
    slide_count: int,
    issues: list[str],
) -> None:
    if manifest.get("source") != "actual-render-surface-calls":
        issues.append(
            "reconstruction.native_object_manifest must come from "
            "actual-render-surface-calls"
        )
    slides = manifest.get("slides")
    if not isinstance(slides, dict):
        issues.append("reconstruction.native_object_manifest.slides must be an object")
        return
    expected = {str(number) for number in range(1, slide_count + 1)}
    if set(slides) != expected:
        issues.append(
            "reconstruction.native_object_manifest slide keys must match "
            f"1..{slide_count}"
        )
        return
    for slide_number in range(1, slide_count + 1):
        row = slides[str(slide_number)]
        objects = row.get("objects") if isinstance(row, dict) else None
        if not isinstance(objects, list) or not objects:
            issues.append(
                f"native object manifest slide {slide_number} has no render objects"
            )
            continue
        if not any(_is_editable_text(item) for item in objects):
            issues.append(
                f"native object manifest slide {slide_number} has no editable text"
            )


def _validate_no_source_slide_embedding(
    pptx_path: Path | None,
    source_paths: list[Path | None],
    issues: list[str],
) -> None:
    """Reject the exact generated slide PNG bytes as a PPTX media shortcut."""

    if pptx_path is None:
        return
    source_hashes = {
        _sha256_file(path)
        for path in source_paths
        if path is not None and path.is_file()
    }
    try:
        with zipfile.ZipFile(pptx_path) as archive:
            for name in archive.namelist():
                if not name.startswith("ppt/media/") or name.endswith("/"):
                    continue
                digest = hashlib.sha256(archive.read(name)).hexdigest()
                if digest in source_hashes:
                    issues.append(
                        "reconstruction.output_pptx embeds an exact generated source "
                        f"slide image as media: {name}"
                    )
    except (OSError, zipfile.BadZipFile):
        return


def _validate_orchestration_state(
    state: dict[str, Any],
    quality_level: str,
    slide_count: int,
    issues: list[str],
) -> None:
    expected_slides = list(range(1, slide_count + 1))
    if state.get("qualityLevel") != quality_level:
        issues.append(
            "reconstruction.orchestration_state qualityLevel must match "
            "reconstruction.quality_level"
        )
    if state.get("slides") != expected_slides:
        issues.append(
            f"reconstruction.orchestration_state.slides must be {expected_slides}"
        )
    limits = state.get("limits")
    if isinstance(limits, dict) and limits.get("maxWaveSize") not in (None, 5):
        issues.append("reconstruction.orchestration_state.limits.maxWaveSize must be 5")
    if isinstance(limits, dict) and limits.get("maxIterations") not in (None, 2):
        issues.append(
            "reconstruction.orchestration_state.limits.maxIterations must be 2"
        )


def _validate_crop_plan(plan: dict[str, Any], issues: list[str]) -> None:
    if plan.get("schema_version") == "1.0.0" and isinstance(plan.get("crops"), list):
        return
    if isinstance(plan.get("slides"), dict):
        return
    issues.append(
        "reconstruction.crop_plan must contain the explicit v1 crops array or "
        "the structured slides map"
    )


def _validate_slide_keyed_evidence(
    payload: dict[str, Any],
    slide_count: int,
    label: str,
    issues: list[str],
) -> None:
    slides = payload.get("slides")
    expected = {str(number) for number in range(1, slide_count + 1)}
    if not isinstance(slides, dict) or set(slides) != expected:
        issues.append(f"{label}.slides must contain exactly 1..{slide_count}")


def _validate_qa_evidence(
    payload: dict[str, Any],
    slide_count: int,
    issues: list[str],
) -> None:
    _validate_slide_keyed_evidence(
        payload,
        slide_count,
        "reconstruction.qa_evidence_summary",
        issues,
    )
    slides = payload.get("slides")
    if not isinstance(slides, dict):
        return
    for slide_number in range(1, slide_count + 1):
        row = slides.get(str(slide_number))
        if not isinstance(row, dict):
            continue
        if row.get("exists") is not True or row.get("hashesValid") is not True:
            issues.append(
                f"reconstruction.qa_evidence_summary slide {slide_number} "
                "must exist with valid hashes"
            )
        if str(row.get("status", "")).lower() != "pass":
            issues.append(
                f"reconstruction.qa_evidence_summary slide {slide_number} "
                "must record pass"
            )


def _validate_render_trace(
    trace: dict[str, Any],
    reconstruction: dict[str, Any],
    artifacts: dict[str, Path],
    slide_count: int,
    issues: list[str],
) -> None:
    required_values = {
        "quality": "reconstruction",
        "target": "both",
        "requireQa": True,
        "requireReconstruction": True,
        "strictMode": True,
        "invokedByPipeline": True,
        "enforcementDisabled": False,
    }
    for key, expected in required_values.items():
        if trace.get(key) != expected:
            issues.append(f"reconstruction.render_trace.{key} must be {expected!r}")
    if Path(str(trace.get("skillRoot", ""))).name != RENDERER_SKILL:
        issues.append(
            "reconstruction.render_trace.skillRoot must identify slide-image-dual-render"
        )
    if trace.get("dependencyMissingPackages") not in ([], None):
        issues.append(
            "reconstruction.render_trace dependencyMissingPackages must be empty"
        )
    if trace.get("dependencyResolutionMode") != "cli":
        issues.append(
            "reconstruction.render_trace dependencyResolutionMode must be cli"
        )
    crop_plan_path = artifacts.get("reconstruction.crop_plan")
    if crop_plan_path is not None:
        expected_node_path = crop_plan_path.parent.parent / "node_modules"
        raw_node_path = trace.get("nodePathUsed")
        if (
            not isinstance(raw_node_path, str)
            or not raw_node_path
            or Path(raw_node_path).resolve() != expected_node_path.resolve()
        ):
            issues.append(
                "reconstruction.render_trace.nodePathUsed must identify the "
                "project-local node_modules passed through --node-path"
            )
    if slide_count > 5 and trace.get("allowLargeBatch") is not True:
        issues.append(
            "reconstruction.render_trace final build must allow the explicit large batch"
        )

    for key in (
        "validation",
        "preflightValidation",
        "postbuildValidation",
        "finalValidation",
        "reconstructionValidation",
    ):
        value = trace.get(key)
        if not isinstance(value, dict) or value.get("passed") is not True:
            issues.append(f"reconstruction.render_trace.{key}.passed must be true")
    qa_summary = trace.get("qaSummary")
    if not isinstance(qa_summary, dict) or qa_summary.get("passed") is not True:
        issues.append("reconstruction.render_trace.qaSummary.passed must be true")
    package = trace.get("pptxPackageValidation")
    if not isinstance(package, dict) or package.get("passed") is not True:
        issues.append(
            "reconstruction.render_trace.pptxPackageValidation.passed must be true"
        )

    _trace_path_matches(
        trace.get("pptxOut"),
        artifacts.get("reconstruction.output_pptx"),
        "pptxOut",
        issues,
    )
    _trace_path_matches(
        trace.get("htmlOut"),
        artifacts.get("reconstruction.output_html"),
        "htmlOut",
        issues,
    )
    _trace_path_matches(
        trace.get("cropPlanPath"),
        artifacts.get("reconstruction.crop_plan"),
        "cropPlanPath",
        issues,
    )
    _trace_path_matches(
        trace.get("cropManifestPath"),
        artifacts.get("reconstruction.crop_manifest"),
        "cropManifestPath",
        issues,
    )
    if trace.get("cropPlanHash") != reconstruction["crop_plan"]["sha256"]:
        issues.append("reconstruction.render_trace cropPlanHash mismatch")
    if trace.get("cropManifestHash") != reconstruction["crop_manifest"]["sha256"]:
        issues.append("reconstruction.render_trace cropManifestHash mismatch")
    if (
        trace.get("nativeObjectManifestHash")
        != reconstruction["native_object_manifest"]["sha256"]
    ):
        issues.append("reconstruction.render_trace nativeObjectManifestHash mismatch")
    if (
        trace.get("cropCoverageSummaryHash")
        != reconstruction["crop_coverage_summary"]["sha256"]
    ):
        issues.append("reconstruction.render_trace cropCoverageSummaryHash mismatch")
    if (
        trace.get("qaEvidenceSummaryHash")
        != reconstruction["qa_evidence_summary"]["sha256"]
    ):
        issues.append("reconstruction.render_trace qaEvidenceSummaryHash mismatch")


def _trace_path_matches(
    raw_path: Any,
    expected: Path | None,
    label: str,
    issues: list[str],
) -> None:
    if expected is None:
        return
    if not isinstance(raw_path, str) or not raw_path:
        issues.append(f"reconstruction.render_trace.{label} is missing")
        return
    if Path(raw_path).resolve() != expected.resolve():
        issues.append(f"reconstruction.render_trace.{label} path mismatch")


def _is_editable_text(value: Any) -> bool:
    if (
        not isinstance(value, dict)
        or value.get("type") != "text"
        or value.get("editable") is False
    ):
        return False
    try:
        return int(value.get("textLength", 0)) > 0
    except (TypeError, ValueError):
        return False


def _validate_openability_report(
    report: dict[str, Any],
    expected_pptx_hash: str,
    issues: list[str],
) -> None:
    summary = report.get("summary")
    if report.get("passed") is not True:
        issues.append("reconstruction.openability_report.passed must be true")
    if not isinstance(summary, dict) or summary.get("errorCount") != 0:
        issues.append(
            "reconstruction.openability_report.summary.errorCount must be zero"
        )
    if report.get("sha256") != expected_pptx_hash:
        issues.append(
            "reconstruction.openability_report sha256 must match the reconstructed PPTX"
        )


def _validate_qa_summary(
    summary: dict[str, Any],
    manifest_qa: dict[str, Any],
    slide_count: int,
    issues: list[str],
) -> None:
    expected_slides = list(range(1, slide_count + 1))
    comparisons = (
        ("failed", "fail_count"),
        ("blockingIssues", "blocking_count"),
        ("needsPolish", "needs_polish_count"),
    )
    if summary.get("slidesRequested") != expected_slides:
        issues.append(f"visual_qa.summary.slidesRequested must be {expected_slides}")
    for summary_key, manifest_key in comparisons:
        if summary.get(summary_key) != manifest_qa[manifest_key]:
            issues.append(
                f"visual_qa.summary.{summary_key} does not match "
                f"visual_qa.{manifest_key}"
            )


def _validate_final_visual_qa_evidence(
    payload: dict[str, Any],
    artifacts: dict[str, Path],
    summary: dict[str, Any],
    slide_count: int,
    issues: list[str],
) -> None:
    """Bind final Visual QA evidence to the delivered PPTX, HTML, and source PNGs."""

    pptx = artifacts.get("reconstruction.output_pptx")
    html = artifacts.get("reconstruction.output_html")
    if pptx is None or html is None:
        issues.append("completed run requires final PPTX and HTML Visual QA inputs")
        return
    if pptx.parent.name.lower() != "out" or html.parent != pptx.parent:
        issues.append(
            "final PPTX and HTML must share the pngtopptx-project/out directory"
        )
        return

    project = pptx.parent.parent.resolve()
    summary_project = summary.get("project")
    if (
        not isinstance(summary_project, str)
        or Path(summary_project).resolve() != project
    ):
        issues.append("visual_qa.summary.project must match the final project root")

    expected_pptx_hash = _sha256_file(pptx)
    expected_html_hash = _sha256_file(html)
    actual_statuses: list[str] = []
    blocking_issues = 0
    summary_rows = summary.get("slides")
    if not isinstance(summary_rows, list) or len(summary_rows) != slide_count:
        issues.append(
            f"visual_qa.summary.slides must contain {slide_count} official per-slide rows"
        )
        summary_rows = []
    rows_by_slide = {
        row.get("slide"): row
        for row in summary_rows
        if isinstance(row, dict) and isinstance(row.get("slide"), int)
    }

    for index in range(slide_count):
        slide_number = index + 1
        label = f"visual_qa.final.slide{slide_number}"
        visual_dir = project / "work" / f"slide{slide_number:02d}" / "visual_qa"
        paths = {
            "source": visual_dir / "source.png",
            "pptx_raster": visual_dir / "pptx_raster.png",
            "html_screenshot": visual_dir / "html_screenshot.png",
            "pptx_diff": visual_dir / "pptx_diff.png",
            "html_diff": visual_dir / "html_diff.png",
            "pptx_edge_diff": visual_dir / "pptx_edge_diff.png",
            "html_edge_diff": visual_dir / "html_edge_diff.png",
            "metrics": visual_dir / "visual_metrics.json",
            "report": visual_dir / "visual_polish_report.md",
            "fixes": visual_dir / "visual_polish_fixes.json",
            "pptx_metadata": visual_dir / "pptx_raster_metadata.json",
            "html_metadata": visual_dir / "html_screenshot_metadata.json",
        }
        missing = [name for name, path in paths.items() if not path.is_file()]
        if missing:
            issues.append(f"{label} is missing required artifacts: {missing}")
            continue

        source_artifact = artifacts.get(f"image_generation.slides[{index}].source_png")
        if source_artifact is None:
            issues.append(f"{label} cannot resolve its selected source PNG")
            continue
        source_hash = _sha256_file(source_artifact)
        if _sha256_file(paths["source"]) != source_hash:
            issues.append(
                f"{label}.source.png does not match the selected ImageGen PNG"
            )

        pptx_metadata = _json_object(
            paths["pptx_metadata"], f"{label}.pptx_metadata", issues
        )
        html_metadata = _json_object(
            paths["html_metadata"], f"{label}.html_metadata", issues
        )
        metrics = _json_object(paths["metrics"], f"{label}.metrics", issues)
        fixes = _json_object(paths["fixes"], f"{label}.fixes", issues)
        if (
            pptx_metadata is None
            or html_metadata is None
            or metrics is None
            or fixes is None
        ):
            continue

        _validate_final_capture_metadata(
            pptx_metadata,
            label=f"{label}.pptx_metadata",
            input_key="pptx",
            input_hash_key="pptxSha256",
            expected_input=pptx,
            expected_input_hash=expected_pptx_hash,
            expected_output=paths["pptx_raster"],
            slide_number=slide_number,
            project=project,
            issues=issues,
        )
        _validate_final_capture_metadata(
            html_metadata,
            label=f"{label}.html_metadata",
            input_key="html",
            input_hash_key="htmlSha256",
            expected_input=html,
            expected_input_hash=expected_html_hash,
            expected_output=paths["html_screenshot"],
            slide_number=slide_number,
            project=project,
            issues=issues,
        )

        hashes = metrics.get("hashes")
        expected_hashes = {
            "source": source_hash,
            "visual_qa_source": source_hash,
            "pptx_raster": _sha256_file(paths["pptx_raster"]),
            "html_screenshot": _sha256_file(paths["html_screenshot"]),
        }
        if not isinstance(hashes, dict):
            issues.append(f"{label}.metrics.hashes must be an object")
        else:
            for key, expected_hash in expected_hashes.items():
                if hashes.get(key) != expected_hash:
                    issues.append(f"{label}.metrics.hashes.{key} mismatch")
        if metrics.get("slide") != slide_number:
            issues.append(f"{label}.metrics.slide mismatch")
        if metrics.get("mode") != "qa-polish":
            issues.append(f"{label}.metrics.mode must be qa-polish")
        status = metrics.get("overallStatus", metrics.get("status"))
        if status not in {"pass", "needs_polish", "fail"}:
            issues.append(f"{label}.metrics has invalid status {status!r}")
        else:
            actual_statuses.append(status)
        metric_issues = metrics.get("issues")
        if isinstance(metric_issues, list):
            blocking_issues += sum(
                1
                for item in metric_issues
                if isinstance(item, dict) and item.get("severity") == "blocking"
            )
        if fixes.get("slide") != slide_number or fixes.get("status") != status:
            issues.append(f"{label}.fixes must match the final metrics status")

        summary_row = rows_by_slide.get(slide_number)
        if not isinstance(summary_row, dict):
            issues.append(f"{label} is missing from visual_qa.summary.slides")
        elif (
            summary_row.get("status") != status
            or summary_row.get("hasMetrics") is not True
            or summary_row.get("hasFixes") is not True
        ):
            issues.append(f"{label} summary row does not match final metrics/fixes")

    counts = summary.get("counts")
    if isinstance(counts, dict):
        expected_counts = {
            "pass": actual_statuses.count("pass"),
            "needs_polish": actual_statuses.count("needs_polish"),
            "fail": actual_statuses.count("fail"),
            "missing": slide_count - len(actual_statuses),
        }
        for key, expected in expected_counts.items():
            if counts.get(key) != expected:
                issues.append(f"visual_qa.summary.counts.{key} must be {expected}")
    else:
        issues.append("visual_qa.summary.counts must be an object")
    if summary.get("blockingIssues") != blocking_issues:
        issues.append(
            "visual_qa.summary.blockingIssues must match final per-slide metrics"
        )


def _validate_final_capture_metadata(
    metadata: dict[str, Any],
    *,
    label: str,
    input_key: str,
    input_hash_key: str,
    expected_input: Path,
    expected_input_hash: str,
    expected_output: Path,
    slide_number: int,
    project: Path,
    issues: list[str],
) -> None:
    raw_input = metadata.get(input_key)
    input_path = Path(raw_input) if isinstance(raw_input, str) else None
    if input_path is not None and not input_path.is_absolute():
        input_path = project / input_path
    if input_path is None or input_path.resolve() != expected_input.resolve():
        issues.append(f"{label}.{input_key} must reference the final deliverable")
    if metadata.get(input_hash_key) != expected_input_hash:
        issues.append(f"{label}.{input_hash_key} must match the final deliverable")
    if metadata.get("diagnosticOnly") is not True:
        issues.append(f"{label}.diagnosticOnly must be true")
    if metadata.get("sourceSlideId") != slide_number:
        issues.append(f"{label}.sourceSlideId must be {slide_number}")
    if metadata.get("physicalSlideIndex") != slide_number:
        issues.append(f"{label}.physicalSlideIndex must be {slide_number}")
    if metadata.get("htmlSlideIndex") != slide_number:
        issues.append(f"{label}.htmlSlideIndex must be {slide_number}")
    if metadata.get("mappingMode") != "source-slides-sequential":
        issues.append(f"{label}.mappingMode must prove --source-slides execution")
    if metadata.get("outputSha256") != _sha256_file(expected_output):
        issues.append(f"{label}.outputSha256 mismatch")


def _content_hash(payload: dict[str, Any]) -> str:
    value = dict(payload)
    value.pop("content_hash", None)
    return content_sha256(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _report(
    payload: dict[str, Any],
    issues: list[str],
    completion_issues: list[str],
) -> dict[str, Any]:
    contract_valid = not issues
    completion_ready = (
        contract_valid
        and payload.get("status") == "COMPLETED"
        and not completion_issues
    )
    return {
        "valid": contract_valid,
        "contract_valid": contract_valid,
        "completion_ready": completion_ready,
        "status": payload.get("status"),
        "workflow_id": payload.get("workflow_id"),
        "slide_count": (
            payload.get("architect", {}).get("slide_count")
            if isinstance(payload.get("architect"), dict)
            else None
        ),
        "issues": issues,
        "completion_issues": completion_issues,
    }


def _error(code: str, message: str, path: Path) -> DeckCompilerError:
    return DeckCompilerError(
        code,
        "codex_pptx_generation_run",
        message,
        path.as_posix(),
        remediation_hint=(
            "Use the live pptx-generator-workflow Skill, preserve its execution evidence, "
            "and reseal the run."
        ),
    )


__all__ = [
    "ARCHITECT_SKILL",
    "IMAGE_SKILL",
    "IMAGE_TOOL",
    "RECONSTRUCTION_SKILL",
    "RENDERER_SKILL",
    "SCHEMA_NAME",
    "VISUAL_QA_SKILL",
    "seal_codex_run_manifest",
    "validate_codex_run_manifest",
    "validate_codex_run_manifest_payload",
]
