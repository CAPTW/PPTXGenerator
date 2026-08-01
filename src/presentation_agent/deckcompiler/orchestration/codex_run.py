"""Seal and validate live Codex ImageGen-to-PNGtoPPTX execution evidence."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..errors import DeckCompilerError
from ..identity import content_sha256
from ..manifest_io import read_json, write_json
from ..schemas import validator_for
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
        raise _error("DC_CODEX_RUN_DRAFT_MISSING", f"Codex run draft is missing: {draft}", draft)
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
    for issue in sorted(validator.iter_errors(payload), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in issue.path) or "$"
        issues.append(f"schema:{location}: {issue.message}")
    if issues:
        return _report(payload, issues, completion_issues)

    expected_content_hash = _content_hash(payload)
    if payload["content_hash"] != expected_content_hash:
        issues.append("content_hash does not match canonical manifest content")

    if expected_workflow_id is not None and payload["workflow_id"] != expected_workflow_id:
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
        issues.append("image requested_slide_count does not match architect slide_count")
    if image["completed_slide_count"] != slide_count:
        issues.append("image completed_slide_count does not match architect slide_count")
    if len(image["slides"]) != slide_count:
        issues.append("image slide record count does not match architect slide_count")
    if ordered != list(range(1, slide_count + 1)):
        issues.append(f"image slide order must be contiguous 1..{slide_count}, got {ordered}")
    if len({row["source_png"]["sha256"] for row in image["slides"]}) != slide_count:
        issues.append("selected source PNG hashes must be unique per slide")

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
            completion_issues.append("completed run requires visual_qa.blocking_count 0")
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


def _artifact_references(payload: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    architect = payload.get("architect")
    if isinstance(architect, dict):
        for key in ("workflow_design", "blueprint", "design_system", "approval_record"):
            value = architect.get(key)
            if isinstance(value, dict):
                yield f"architect.{key}", value

    image = payload.get("image_generation")
    if isinstance(image, dict):
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
        for key in ("summary", "contact_sheet"):
            value = visual_qa.get(key)
            if isinstance(value, dict):
                yield f"visual_qa.{key}", value

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

    source_dimensions: list[tuple[int, int]] = []
    for index, slide in enumerate(payload["image_generation"]["slides"]):
        prefix = f"image_generation.slides[{index}]"
        prompt = _json_object(artifacts.get(f"{prefix}.prompt"), f"{prefix}.prompt", issues)
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
        if inspection is not None and str(inspection.get("status", "")).upper() != "PASS":
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
                issues.append(
                    f"selected source PNG must be 16:9, got {width}x{height}"
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
        issues.append(
            "reconstruction.orchestration_state.limits.maxWaveSize must be 5"
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
    if trace.get("nativeObjectManifestHash") != reconstruction["native_object_manifest"]["sha256"]:
        issues.append("reconstruction.render_trace nativeObjectManifestHash mismatch")
    if trace.get("cropCoverageSummaryHash") != reconstruction["crop_coverage_summary"]["sha256"]:
        issues.append("reconstruction.render_trace cropCoverageSummaryHash mismatch")
    if trace.get("qaEvidenceSummaryHash") != reconstruction["qa_evidence_summary"]["sha256"]:
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
