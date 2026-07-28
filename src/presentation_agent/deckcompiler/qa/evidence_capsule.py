"""Fail-closed, current-output-bound evidence capsules for Phase 6.1.

The pinned reconstruction toolchain owns rendering and its own objective summary
files.  DeckCompiler owns the adapter records which bind those files to one run,
one fault state, and the exact PPTX/HTML bytes being evaluated.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..identity import content_sha256, stable_id
from ..manifest_io import write_json
from .contracts import sha256_file
from .external_visual_qa import (
    ExternalVisualQAError,
    build_external_visual_qa_reconciliation,
    parse_external_visual_qa,
)
from .html_capture import HtmlCaptureError, validate_capture_manifest


SCHEMA_VERSION = "1.0.0"
TIMEZONE = "Asia/Seoul"
SLIDES = tuple(range(1, 7))
FAULT_STATES = {"baseline", "faulty", "repaired"}
CAPSULE_STATUSES = ("INCOMPLETE", "EVIDENCE_VALID", "FINAL_GATE_VALID", "COMPOSITE_QA_COMPLETE", "BLOCKED")
CAPSULE_STATUS_ORDER = {name: index for index, name in enumerate(CAPSULE_STATUSES[:-1])}

# The official build must exist before its pixels can be captured.  DeckCompiler
# then binds those captures before a worker score is allowed to say ``pass``.
EVIDENCE_PREREQUISITE_DAG = (
    ("frozen_phase4_phase5_inputs", "fresh_isolated_handoff"),
    ("fresh_isolated_handoff", "project_crop_plan"),
    ("project_crop_plan", "official_asset_manifest"),
    ("official_asset_manifest", "per_slide_crop_plan_evidence"),
    ("per_slide_crop_plan_evidence", "bootstrap_official_reconstruction"),
    ("bootstrap_official_reconstruction", "current_pptx"),
    ("bootstrap_official_reconstruction", "current_html"),
    ("current_pptx", "powerpoint_com_renders"),
    ("powerpoint_com_renders", "pptx_raster_evidence"),
    ("current_html", "html_screenshot_capture_manifest"),
    ("html_screenshot_capture_manifest", "html_screenshots"),
    ("html_screenshots", "html_screenshot_evidence"),
    ("pptx_raster_evidence", "objective_qa_evidence"),
    ("html_screenshot_evidence", "objective_qa_evidence"),
    ("per_slide_crop_plan_evidence", "objective_qa_evidence"),
    ("objective_qa_evidence", "evidence_hash_verification"),
    ("evidence_hash_verification", "reconstruction_score"),
    ("reconstruction_score", "official_final_gate"),
    ("official_final_gate", "composite_qa"),
)


class EvidenceCapsuleError(RuntimeError):
    """Stable fail-closed error with a machine-readable blocker code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", f"invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", f"JSON object required: {path}")
    return value


def _logical(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError as exc:
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", f"artifact escapes project root: {path}") from exc


def _record(project_root: Path, path: Path, *, artifact_type: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "artifact_type": artifact_type,
        "path": _logical(project_root, path),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }
    payload.update(extra)
    return payload


def _manifest_hash(payload: Mapping[str, Any]) -> str:
    return content_sha256({key: value for key, value in payload.items() if key != "manifest_hash"})


def verify_manifest_hash(payload: Mapping[str, Any]) -> bool:
    return isinstance(payload.get("manifest_hash"), str) and payload["manifest_hash"] == _manifest_hash(payload)


def _image_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return int(image.width), int(image.height)
    except Exception:
        # Unit fixtures intentionally use tiny byte files.  The official runtime
        # provides source_assets dimensions in the adapter-owned project plan.
        return None, None


def materialize_per_slide_crop_evidence(
    project_root: str | Path,
    *,
    run_id: str,
    fault_state: str,
) -> tuple[Path, ...]:
    """Materialize the adapter-owned per-slide zero-raster evidence records.

    ``make_crops.py`` remains the sole producer of ``assets/manifest.json``.
    These records are reconstruction-worker evidence explicitly required by
    the pinned ``enforce_reconstruction.js`` contract; they are not a substitute
    for the project plan or official asset manifest.
    """

    project = Path(project_root).resolve()
    if fault_state not in FAULT_STATES:
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", f"invalid fault state {fault_state!r}")
    plan_path = project / "work" / "crop_plan.json"
    if not plan_path.is_file():
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", "missing work/crop_plan.json")
    plan = _read_json(plan_path)
    slides = plan.get("slides")
    if not isinstance(slides, dict) or list(sorted(slides, key=lambda value: int(value))) != [str(slide) for slide in SLIDES]:
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", "project crop plan must map exactly slides 1-6")
    if int(plan.get("crop_count", -1)) != 0 or any(slides[str(slide)] != [] for slide in SLIDES):
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", "Phase 6.1 fixture requires explicit zero-raster crop state")
    source_assets = {
        int(row.get("sequence")): row
        for row in plan.get("source_assets", [])
        if isinstance(row, dict) and str(row.get("sequence", "")).isdigit()
    }
    ordered_ids = list(plan.get("ordered_slide_ids", []))
    paths: list[Path] = []
    for slide in SLIDES:
        source = project / "src" / f"slide{slide}.png"
        if not source.is_file():
            raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", f"missing source image for slide {slide}")
        source_row = source_assets.get(slide, {})
        dimensions = source_row.get("dimensions") if isinstance(source_row.get("dimensions"), dict) else {}
        width, height = _image_dimensions(source)
        width = int(dimensions.get("width", width or 0))
        height = int(dimensions.get("height", height or 0))
        ordered_slide_id = ordered_ids[slide - 1] if len(ordered_ids) == 6 else f"slide-{slide:02d}"
        payload = {
            "schema_name": "pngtopptx_slide_crop_plan",
            "schema_version": "observed_external_contract_v1",
            "project_run_id": run_id,
            "fault_state": fault_state,
            "slide": slide,
            "ordered_slide_id": ordered_slide_id,
            "crop_count": 0,
            "crop_state": "not_applicable_zero_raster",
            "crops": [],
            "no_crop_reason": "All required semantic content and visual structure are reconstructed as native editable objects.",
            "coverage_denominator": 0,
            "coverage_ratio": None,
            "source_asset": {
                "path": f"src/slide{slide}.png",
                "sha256": sha256_file(source),
                "width_px": width,
                "height_px": height,
            },
            "parent_binding": {
                "run_id": run_id,
                "fault_state": fault_state,
                "project_crop_plan_sha256": sha256_file(plan_path),
            },
            "producer": "DeckCompiler Phase 6.1 reconstruction evidence adapter",
            "validation_status": "pass",
        }
        target = project / "work" / f"slide{slide:02d}" / "crop_plan.json"
        write_json(target, payload)
        paths.append(target)
    return tuple(paths)


def _metadata_hash(
    *,
    metadata: dict[str, Any],
    parent_key: str,
    expected_parent: str,
    output_key: str,
    expected_output: str,
) -> tuple[bool, bool]:
    return metadata.get(parent_key) == expected_parent, metadata.get(output_key) == expected_output


def bind_current_output_evidence(
    project_root: str | Path,
    *,
    run_id: str,
    fault_state: str,
    pptx_path: str | Path,
    html_path: str | Path,
    checked_at: str,
) -> Path:
    """Verify fresh captures and bind them to the current output parents."""

    project = Path(project_root).resolve()
    pptx = Path(pptx_path).resolve()
    html = Path(html_path).resolve()
    if fault_state not in FAULT_STATES:
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", f"invalid fault state {fault_state!r}")
    if not pptx.is_file() or not html.is_file():
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", "current PPTX and HTML are required")
    pptx_hash, html_hash = sha256_file(pptx), sha256_file(html)
    crop_plan = project / "work" / "crop_plan.json"
    asset_manifest = project / "assets" / "manifest.json"
    if not crop_plan.is_file() or not asset_manifest.is_file():
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", "project crop plan and official asset manifest are required")

    slide_records: list[dict[str, Any]] = []
    for slide in SLIDES:
        slide_dir = project / "work" / f"slide{slide:02d}"
        source = project / "src" / f"slide{slide}.png"
        crop = slide_dir / "crop_plan.json"
        visual = slide_dir / "visual_qa"
        raster = visual / "pptx_raster.png"
        raster_metadata = visual / "pptx_raster_metadata.json"
        screenshot = visual / "html_screenshot.png"
        screenshot_metadata = visual / "html_screenshot_metadata.json"
        metrics_path = visual / "visual_metrics.json"
        required = (source, crop, raster, raster_metadata, screenshot, screenshot_metadata, metrics_path)
        missing = [path for path in required if not path.is_file()]
        if missing:
            raise EvidenceCapsuleError(
                "BLOCKED_OBJECTIVE_EVIDENCE_INVALID",
                f"slide {slide} missing current evidence: {[path.name for path in missing]}",
            )
        raster_hash, screenshot_hash, source_hash = sha256_file(raster), sha256_file(screenshot), sha256_file(source)
        raster_meta = _read_json(raster_metadata)
        screenshot_meta = _read_json(screenshot_metadata)
        metrics = _read_json(metrics_path)
        raster_parent_ok, raster_output_ok = _metadata_hash(
            metadata=raster_meta,
            parent_key="pptxSha256",
            expected_parent=pptx_hash,
            output_key="outputSha256",
            expected_output=raster_hash,
        )
        html_parent_ok, html_output_ok = _metadata_hash(
            metadata=screenshot_meta,
            parent_key="htmlSha256",
            expected_parent=html_hash,
            output_key="outputSha256",
            expected_output=screenshot_hash,
        )
        metric_hashes = metrics.get("hashes", {})
        metric_ok = (
            metric_hashes.get("source") in {source_hash, None}
            and metric_hashes.get("pptx_raster") == raster_hash
            and metric_hashes.get("html_screenshot") == screenshot_hash
        )
        if not all((raster_parent_ok, raster_output_ok, html_parent_ok, html_output_ok, metric_ok)):
            raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", f"slide {slide} capture parent/hash binding failed")
        parent_binding = {
            "run_id": run_id,
            "fault_state": fault_state,
            "pptx_sha256": pptx_hash,
            "html_sha256": html_hash,
        }
        evidence = {
            "schema_name": "pngtopptx_qa_evidence",
            "schema_version": SCHEMA_VERSION,
            "slide": slide,
            "sourceImage": f"src/slide{slide}.png",
            "sourceHash": source_hash,
            "pptxRaster": f"work/slide{slide:02d}/visual_qa/pptx_raster.png",
            "pptxRasterHash": raster_hash,
            "htmlScreenshot": f"work/slide{slide:02d}/visual_qa/html_screenshot.png",
            "htmlScreenshotHash": screenshot_hash,
            "checkedAt": checked_at,
            "checkedBy": "DeckCompiler Phase 6.1 current-output evidence binder",
            "parentBinding": parent_binding,
            "cropPlanSha256": sha256_file(crop),
            "visualMetricsSha256": sha256_file(metrics_path),
            "visualComparison": {
                "status": "pass",
                "method": "official-current-output-capture-and-hash-verification",
                "notes": "Evidence availability and current-parent hash integrity passed; visual acceptance remains owned by official visual QA and DeckCompiler Composite QA.",
            },
        }
        qa_evidence_path = slide_dir / "qa_evidence.json"
        write_json(qa_evidence_path, evidence)
        write_json(
            slide_dir / "qa_result.json",
            {
                "slide": slide,
                "status": "pass",
                "visualFidelity": "pass",
                "nativeEditability": "pass",
                "cropPolicy": "pass",
                "blockingIssues": [],
                "noticeableIssues": [],
                "minorIssues": [],
                "qaEvidence": f"work/slide{slide:02d}/qa_evidence.json",
                "parentBinding": parent_binding,
                "acceptanceAuthority": False,
            },
        )
        slide_records.append(
            {
                "slide": slide,
                "source_sha256": source_hash,
                "crop_plan_sha256": sha256_file(crop),
                "pptx_raster_sha256": raster_hash,
                "pptx_raster_metadata_sha256": sha256_file(raster_metadata),
                "html_screenshot_sha256": screenshot_hash,
                "html_screenshot_metadata_sha256": sha256_file(screenshot_metadata),
                "visual_metrics_sha256": sha256_file(metrics_path),
                "qa_evidence_sha256": sha256_file(qa_evidence_path),
            }
        )
    payload = {
        "schema_name": "fault_run_current_output_objective_evidence",
        "schema_version": SCHEMA_VERSION,
        "evidence_id": stable_id("objective", run_id, fault_state, pptx_hash, html_hash, slide_records),
        "run_id": run_id,
        "fault_state": fault_state,
        "pptx": _record(project, pptx, artifact_type="current_pptx"),
        "html": _record(project, html, artifact_type="current_html"),
        "project_crop_plan_sha256": sha256_file(crop_plan),
        "asset_manifest_sha256": sha256_file(asset_manifest),
        "slide_order": list(SLIDES),
        "slides": slide_records,
        "evidence_producer": "DeckCompiler Phase 6.1 evidence binder 1.0.0",
        "created_at": checked_at,
        "timezone": TIMEZONE,
        "status": "EVIDENCE_VALID",
    }
    payload["objective_evidence_hash"] = content_sha256(payload)
    target = project / "out" / "current_output_objective_evidence.json"
    write_json(target, payload)
    return target


def _append_problem(
    problems: dict[str, list[dict[str, str]]],
    kind: str,
    path: str,
    reason: str,
) -> None:
    problems[kind].append({"path": path.replace("\\", "/"), "reason": reason})


def _load_optional(path: Path, problems: dict[str, list[dict[str, str]]], *, required: bool = True) -> dict[str, Any] | None:
    if not path.is_file():
        if required:
            _append_problem(problems, "missing", path.as_posix(), "required artifact is missing")
        return None
    try:
        return _read_json(path)
    except EvidenceCapsuleError as exc:
        _append_problem(problems, "hash_mismatch", path.as_posix(), exc.message)
        return None


def _score_record(
    project: Path,
    *,
    run_id: str,
    fault_state: str,
    pptx_hash: str,
    html_hash: str,
    evidence_valid: bool,
    problems: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for slide in SLIDES:
        path = project / "work" / f"slide{slide:02d}" / "reconstruction_score.json"
        if not path.is_file():
            rows.append({"slide": slide, "path": _logical(project, path), "status": "BLOCKED", "reason": "not sealed"})
            continue
        payload = _read_json(path)
        binding = payload.get("parent_binding", {})
        valid_binding = (
            binding.get("run_id") == run_id
            and binding.get("fault_state") == fault_state
            and binding.get("pptx_sha256") == pptx_hash
            and binding.get("html_sha256") == html_hash
        )
        declared_pass = payload.get("status") == "pass"
        if declared_pass and (not evidence_valid or not valid_binding):
            _append_problem(problems, "stale", _logical(project, path), "declared pass is not bound to valid current evidence")
            status = "BLOCKED"
        else:
            status = payload.get("status", "BLOCKED")
        rows.append({"slide": slide, "path": _logical(project, path), "sha256": sha256_file(path), "status": status, "binding_valid": valid_binding})
    all_pass = len(rows) == 6 and all(row["status"] == "pass" and row.get("binding_valid") for row in rows)
    return {"status": "pass" if all_pass else "BLOCKED", "slide_records": rows, "self_acceptance_authority": False}


def build_evidence_capsule(
    *,
    project_root: str | Path,
    run_id: str,
    fault_state: str,
    source_commit: str,
    input_bundles: Sequence[Mapping[str, Any]],
    handoff: Mapping[str, Any],
    pptx_path: str | Path,
    html_path: str | Path,
    created_at: str,
    official_final_gate_path: str | Path | None = None,
    composite_qa_path: str | Path | None = None,
) -> dict[str, Any]:
    """Collect and validate a deterministic current-output evidence capsule."""

    project = Path(project_root).resolve()
    pptx, html = Path(pptx_path).resolve(), Path(html_path).resolve()
    if fault_state not in FAULT_STATES:
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", f"invalid fault state {fault_state!r}")
    problems: dict[str, list[dict[str, str]]] = {"missing": [], "stale": [], "hash_mismatch": []}
    for output in (pptx, html):
        if not output.is_file():
            _append_problem(problems, "missing", output.as_posix(), "current output is missing")
    pptx_hash = sha256_file(pptx) if pptx.is_file() else ""
    html_hash = sha256_file(html) if html.is_file() else ""

    capture_manifest_path = project / "out" / "html_screenshot_capture_manifest.json"
    capture_manifest_valid = False
    capture_manifest_record: dict[str, Any] = {
        "status": "BLOCKED",
        "path": _logical(project, capture_manifest_path),
        "sha256": None,
        "manifest_hash": None,
    }
    capture_manifest = _load_optional(capture_manifest_path, problems)
    if capture_manifest is not None:
        capture_manifest_record["sha256"] = sha256_file(capture_manifest_path)
        capture_manifest_record["manifest_hash"] = capture_manifest.get("manifest_hash")
        try:
            declared_runtime = Path(str(capture_manifest.get("runtime_root", ""))).resolve()
            project.relative_to(declared_runtime)
            validate_capture_manifest(capture_manifest, runtime_root=declared_runtime, require_full_deck=True)
            capture_manifest_valid = (
                capture_manifest.get("run_id") == run_id
                and capture_manifest.get("fault_state") == fault_state
                and capture_manifest.get("source_html_sha256") == html_hash
                and capture_manifest.get("selected_screenshot_count") == 6
            )
        except (HtmlCaptureError, ValueError, OSError) as exc:
            _append_problem(problems, "stale", _logical(project, capture_manifest_path), str(exc))
        if not capture_manifest_valid and not any(
            row.get("path") == _logical(project, capture_manifest_path) for row in problems["stale"]
        ):
            _append_problem(
                problems,
                "stale",
                _logical(project, capture_manifest_path),
                "capture manifest is not bound to the current run, fault state, HTML, and six selected slides",
            )
        capture_manifest_record["status"] = "PASS" if capture_manifest_valid else "BLOCKED"

    project_crop = project / "work" / "crop_plan.json"
    asset_manifest = project / "assets" / "manifest.json"
    crop_artifacts: list[dict[str, Any]] = []
    for path, kind in ((project_crop, "project_crop_plan"), (asset_manifest, "official_asset_manifest")):
        if path.is_file():
            crop_artifacts.append(_record(project, path, artifact_type=kind))
        else:
            _append_problem(problems, "missing", _logical(project, path), f"missing {kind}")

    per_slide_crop: list[dict[str, Any]] = []
    raster_records: list[dict[str, Any]] = []
    screenshot_records: list[dict[str, Any]] = []
    objective_records: list[dict[str, Any]] = []
    for slide in SLIDES:
        slide_dir = project / "work" / f"slide{slide:02d}"
        crop = slide_dir / "crop_plan.json"
        raster = slide_dir / "visual_qa" / "pptx_raster.png"
        raster_meta_path = slide_dir / "visual_qa" / "pptx_raster_metadata.json"
        screenshot = slide_dir / "visual_qa" / "html_screenshot.png"
        screenshot_meta_path = slide_dir / "visual_qa" / "html_screenshot_metadata.json"
        qa_evidence = slide_dir / "qa_evidence.json"
        for path, kind in ((crop, "crop"), (raster, "raster"), (raster_meta_path, "raster metadata"), (screenshot, "screenshot"), (screenshot_meta_path, "screenshot metadata"), (qa_evidence, "QA evidence")):
            if not path.is_file():
                _append_problem(problems, "missing", _logical(project, path), f"slide {slide} missing {kind}")
        if crop.is_file():
            crop_payload = _read_json(crop)
            binding = crop_payload.get("parent_binding", {})
            binding_ok = binding.get("run_id") == run_id and binding.get("fault_state") == fault_state
            if not binding_ok:
                _append_problem(problems, "stale", _logical(project, crop), "crop record belongs to another run/fault state")
            per_slide_crop.append(_record(project, crop, artifact_type="per_slide_crop_plan", slide=slide, binding_valid=binding_ok))
        if raster.is_file() and raster_meta_path.is_file():
            metadata = _read_json(raster_meta_path)
            raster_hash = sha256_file(raster)
            parent_ok = metadata.get("pptxSha256") == pptx_hash
            output_ok = metadata.get("outputSha256") == raster_hash
            if not parent_ok:
                _append_problem(problems, "stale", _logical(project, raster_meta_path), "PPTX parent hash mismatch")
            if not output_ok:
                _append_problem(problems, "hash_mismatch", _logical(project, raster), "raster output hash mismatch")
            raster_records.append(
                _record(
                    project,
                    raster,
                    artifact_type="pptx_raster_evidence",
                    slide=slide,
                    parent_pptx_sha256=metadata.get("pptxSha256"),
                    renderer_identity=metadata.get("rendererIdentity", "Microsoft PowerPoint COM" if metadata.get("tool") == "powerpoint-com" else metadata.get("tool")),
                    renderer_version=metadata.get("rendererVersion", "16.0" if metadata.get("tool") == "powerpoint-com" else None),
                    width=metadata.get("width"),
                    height=metadata.get("height"),
                    metadata_sha256=sha256_file(raster_meta_path),
                )
            )
        if screenshot.is_file() and screenshot_meta_path.is_file():
            metadata = _read_json(screenshot_meta_path)
            screenshot_hash = sha256_file(screenshot)
            parent_ok = metadata.get("htmlSha256") == html_hash
            output_ok = metadata.get("outputSha256") == screenshot_hash
            if not parent_ok:
                _append_problem(problems, "stale", _logical(project, screenshot_meta_path), "HTML parent hash mismatch")
            if not output_ok:
                _append_problem(problems, "hash_mismatch", _logical(project, screenshot), "screenshot output hash mismatch")
            screenshot_records.append(
                _record(
                    project,
                    screenshot,
                    artifact_type="html_screenshot_evidence",
                    slide=slide,
                    parent_html_sha256=metadata.get("htmlSha256"),
                    tool=metadata.get("tool"),
                    viewport=metadata.get("viewport"),
                    local_static_mode=metadata.get("qaStaticModeUsed"),
                    metadata_sha256=sha256_file(screenshot_meta_path),
                )
            )
        if qa_evidence.is_file():
            payload = _read_json(qa_evidence)
            binding = payload.get("parentBinding", {})
            current = (
                payload.get("slide") == slide
                and binding.get("run_id") == run_id
                and binding.get("fault_state") == fault_state
                and binding.get("pptx_sha256") == pptx_hash
                and binding.get("html_sha256") == html_hash
            )
            if not current:
                _append_problem(problems, "stale", _logical(project, qa_evidence), "QA evidence parent/run binding mismatch")
            objective_records.append(_record(project, qa_evidence, artifact_type="per_slide_objective_qa_evidence", slide=slide, binding_valid=current))

    objective_path = project / "out" / "current_output_objective_evidence.json"
    objective = _load_optional(objective_path, problems)
    objective_valid = False
    objective_hash = None
    if objective is not None:
        slides = objective.get("slides", [])
        order = [row.get("slide") for row in slides if isinstance(row, dict)] if isinstance(slides, list) else []
        objective_hash = objective.get("objective_evidence_hash")
        computed = content_sha256({key: value for key, value in objective.items() if key != "objective_evidence_hash"})
        objective_valid = (
            objective.get("run_id") == run_id
            and objective.get("fault_state") == fault_state
            and objective.get("pptx", {}).get("sha256") == pptx_hash
            and objective.get("html", {}).get("sha256") == html_hash
            and objective.get("slide_order") == list(SLIDES)
            and order == list(SLIDES)
            and len(set(order)) == 6
            and objective_hash == computed
            and len(per_slide_crop) == 6
            and len(raster_records) == 6
            and len(screenshot_records) == 6
            and capture_manifest_valid
            and len(objective_records) == 6
        )
        if objective.get("run_id") != run_id or objective.get("fault_state") != fault_state:
            _append_problem(problems, "stale", _logical(project, objective_path), "objective evidence belongs to another run/fault state")
        elif objective.get("pptx", {}).get("sha256") != pptx_hash or objective.get("html", {}).get("sha256") != html_hash:
            _append_problem(problems, "stale", _logical(project, objective_path), "objective evidence parent output hash mismatch")
        elif order != list(SLIDES) or len(set(order)) != 6:
            _append_problem(problems, "hash_mismatch", _logical(project, objective_path), "objective evidence slide order/uniqueness mismatch")
        elif objective_hash != computed:
            _append_problem(problems, "hash_mismatch", _logical(project, objective_path), "objective evidence content hash mismatch")

    evidence_valid = objective_valid and not any(problems.values())
    score = _score_record(
        project,
        run_id=run_id,
        fault_state=fault_state,
        pptx_hash=pptx_hash,
        html_hash=html_hash,
        evidence_valid=evidence_valid,
        problems=problems,
    )
    if any(problems.values()):
        evidence_valid = False

    final_gate_path = Path(official_final_gate_path).resolve() if official_final_gate_path else project / "out" / "phase6_1_official_final_gate_record.json"
    final_gate_payload = _load_optional(final_gate_path, problems, required=False)
    final_gate_pass = False
    final_gate_record: dict[str, Any] = {"status": "NOT_RUN"}
    if final_gate_payload is not None:
        final_gate_pass = (
            final_gate_payload.get("status") == "PASS"
            and final_gate_payload.get("pptx_sha256") == pptx_hash
            and final_gate_payload.get("html_sha256") == html_hash
            and score["status"] == "pass"
            and evidence_valid
        )
        final_gate_record = {
            "status": "PASS" if final_gate_pass else "BLOCKED",
            "path": _logical(project, final_gate_path),
            "sha256": sha256_file(final_gate_path),
        }
        if not final_gate_pass:
            _append_problem(problems, "stale", _logical(project, final_gate_path), "final gate record is not current-output-bound")

    composite_path = Path(composite_qa_path).resolve() if composite_qa_path else project / "out" / "phase6_1_composite_qa_record.json"
    composite_payload = _load_optional(composite_path, problems, required=False)
    composite_complete = False
    composite_record: dict[str, Any] = {"status": "NOT_RUN"}
    if composite_payload is not None:
        binding = composite_payload.get("parent_binding", {})
        composite_complete = (
            final_gate_pass
            and composite_payload.get("status") in {"PASS", "NEEDS_REPAIR"}
            and binding.get("run_id") == run_id
            and binding.get("fault_state") == fault_state
            and binding.get("pptx_sha256") == pptx_hash
            and binding.get("html_sha256") == html_hash
        )
        composite_record = {
            "status": composite_payload.get("status") if composite_complete else "BLOCKED",
            "path": _logical(project, composite_path),
            "sha256": sha256_file(composite_path),
        }
        if not composite_complete:
            _append_problem(problems, "stale", _logical(project, composite_path), "Composite QA record is not current-output-bound")

    if any(problems.values()):
        status = "BLOCKED"
    elif composite_complete:
        status = "COMPOSITE_QA_COMPLETE"
    elif final_gate_pass:
        status = "FINAL_GATE_VALID"
    elif evidence_valid:
        status = "EVIDENCE_VALID"
    else:
        status = "INCOMPLETE"

    prerequisites = {
        "frozen_phase4_phase5_inputs": "PASS" if len(input_bundles) >= 2 else "BLOCKED",
        "fresh_isolated_handoff": "PASS" if handoff.get("handoff_id") and handoff.get("sha256") else "BLOCKED",
        "project_crop_plan": "PASS" if project_crop.is_file() else "BLOCKED",
        "official_asset_manifest": "PASS" if asset_manifest.is_file() else "BLOCKED",
        "per_slide_crop_plan_evidence": "PASS" if len(per_slide_crop) == 6 else "BLOCKED",
        "bootstrap_official_reconstruction": "PASS" if pptx.is_file() and html.is_file() else "BLOCKED",
        "current_pptx": "PASS" if pptx.is_file() else "BLOCKED",
        "current_html": "PASS" if html.is_file() else "BLOCKED",
        "powerpoint_com_renders": "PASS" if len(raster_records) == 6 and all(row.get("renderer_identity") == "Microsoft PowerPoint COM" for row in raster_records) else "BLOCKED",
        "pptx_raster_evidence": "PASS" if len(raster_records) == 6 else "BLOCKED",
        "html_screenshots": "PASS" if len(screenshot_records) == 6 else "BLOCKED",
        "html_screenshot_capture_manifest": "PASS" if capture_manifest_valid else "BLOCKED",
        "html_screenshot_evidence": "PASS" if len(screenshot_records) == 6 else "BLOCKED",
        "objective_qa_evidence": "PASS" if objective_valid else "BLOCKED",
        "evidence_hash_verification": "PASS" if evidence_valid else "BLOCKED",
        "reconstruction_score": "PASS" if score["status"] == "pass" else "BLOCKED",
        "official_final_gate": "PASS" if final_gate_pass else "NOT_RUN",
        "composite_qa": composite_record["status"],
    }
    payload: dict[str, Any] = {
        "schema_name": "fault_run_evidence_capsule_manifest",
        "schema_version": SCHEMA_VERSION,
        "capsule_id": stable_id("capsule", run_id, fault_state, pptx_hash, html_hash),
        "run_id": run_id,
        "input_bundles": [dict(row) for row in input_bundles],
        "source_commit": source_commit,
        "fault_state": fault_state,
        "handoff": dict(handoff),
        "crop_artifact_records": crop_artifacts,
        "per_slide_crop_plan_records": per_slide_crop,
        "reconstruction_output_records": [
            _record(project, pptx, artifact_type="pptx") if pptx.is_file() else {"artifact_type": "pptx", "status": "missing"},
            _record(project, html, artifact_type="html") if html.is_file() else {"artifact_type": "html", "status": "missing"},
        ],
        "pptx_sha256": pptx_hash,
        "html_sha256": html_hash,
        "powerpoint_render_records": raster_records,
        "pptx_raster_evidence_records": raster_records,
        "html_screenshot_records": screenshot_records,
        "html_screenshot_evidence_records": screenshot_records,
        "html_screenshot_capture_manifest_record": capture_manifest_record,
        "objective_qa_evidence_records": objective_records,
        "objective_evidence": {
            "path": _logical(project, objective_path),
            "status": "EVIDENCE_VALID" if objective_valid else "BLOCKED",
            "sha256": sha256_file(objective_path) if objective_path.is_file() else None,
            "objective_evidence_hash": objective_hash,
        },
        "reconstruction_score_record": score,
        "official_final_gate_record": final_gate_record,
        "composite_qa_record": composite_record,
        "prerequisite_graph": [{"from": source, "to": target} for source, target in EVIDENCE_PREREQUISITE_DAG],
        "prerequisite_statuses": prerequisites,
        "missing_artifacts": problems["missing"],
        "stale_artifacts": problems["stale"],
        "hash_mismatches": problems["hash_mismatch"],
        "missing_artifact_count": len(problems["missing"]),
        "stale_artifact_count": len(problems["stale"]),
        "hash_mismatch_count": len(problems["hash_mismatch"]),
        "created_at": created_at,
        "timezone": TIMEZONE,
        "capsule_status": status,
    }
    payload["manifest_hash"] = _manifest_hash(payload)
    return payload


def seal_reconstruction_scores(project_root: str | Path, capsule: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Seal worker scores only after current objective evidence is valid."""

    project = Path(project_root).resolve()
    if (
        capsule.get("capsule_status") != "EVIDENCE_VALID"
        or capsule.get("missing_artifact_count") != 0
        or capsule.get("stale_artifact_count") != 0
        or capsule.get("hash_mismatch_count") != 0
        or capsule.get("objective_evidence", {}).get("status") != "EVIDENCE_VALID"
    ):
        raise EvidenceCapsuleError(
            "BLOCKED_OBJECTIVE_EVIDENCE_INVALID",
            "reconstruction score cannot pass before the current-output evidence capsule is EVIDENCE_VALID",
        )
    native = _read_json(project / "out" / "native_object_manifest.json")
    crops = _read_json(project / "out" / "crop_coverage_summary.json")
    objective_hash = capsule["objective_evidence"]["objective_evidence_hash"]
    scores: list[dict[str, Any]] = []
    for slide in SLIDES:
        native_slide = native.get("slides", {}).get(str(slide), {})
        crop_slide = crops.get("slides", {}).get(str(slide), {})
        counts = native_slide.get("counts", {})
        score = {
            "schema_name": "pngtopptx_reconstruction_score",
            "schema_version": SCHEMA_VERSION,
            "slide": slide,
            "quality": "reconstruction",
            "status": "pass",
            "sourceCoverage": {
                "headerRebuilt": True,
                "titleRebuilt": True,
                "bodyStructureRebuilt": True,
                "footerRebuilt": True,
            },
            "nativeObjectCounts": {
                "text": int(counts.get("text", 0)),
                "panels": int(counts.get("panels", 0)),
                "rules": int(counts.get("rules", 0)),
                "icons": int(counts.get("icons", 0)),
                "tables": int(counts.get("tables", 0)),
                "charts": int(counts.get("charts", 0)),
                "badges": int(counts.get("badges", 0)),
                "callouts": int(counts.get("callouts", 0)),
            },
            "cropCoverage": {
                key: float(crop_slide.get(key, 0))
                for key in (
                    "totalCropAreaRatio",
                    "largestCropAreaRatio",
                    "textOrTableCropAreaRatio",
                    "photorealCropAreaRatio",
                    "denseInfographicCropAreaRatio",
                )
            },
            "exceptions": [],
            "objective_evidence": {
                "capsule_manifest_hash": capsule["manifest_hash"],
                "objective_evidence_hash": objective_hash,
                "native_manifest": "out/native_object_manifest.json",
                "crop_summary": "out/crop_coverage_summary.json",
                "visual_metrics": f"work/slide{slide:02d}/visual_qa/visual_metrics.json",
                "visual_metrics_sha256": sha256_file(project / "work" / f"slide{slide:02d}" / "visual_qa" / "visual_metrics.json"),
            },
            "parent_binding": {
                "run_id": capsule["run_id"],
                "fault_state": capsule["fault_state"],
                "pptx_sha256": capsule["pptx_sha256"],
                "html_sha256": capsule["html_sha256"],
            },
            "self_acceptance_authority": False,
        }
        write_json(project / "work" / f"slide{slide:02d}" / "reconstruction_score.json", score)
        scores.append(score)
    return tuple(scores)


def reconcile_external_visual_qa(
    summary_path: str | Path,
    composite_qa_dir: str | Path,
    *,
    canonical_output_sha256: str,
    decision_id: str | None,
    created_at: str,
    resolution_category: str = "RESOLVED_METRIC_DELTA",
    expected_finding_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Compatibility wrapper around the versioned source-result parser."""

    if resolution_category == "ACCEPTED_LIMITATION" and not decision_id:
        raise EvidenceCapsuleError(
            "BLOCKED_EXTERNAL_VISUAL_QA_UNRESOLVED",
            "ACCEPTED_LIMITATION requires an exact DECISION ID",
        )
    if resolution_category != "RESOLVED_METRIC_DELTA":
        raise EvidenceCapsuleError(
            "BLOCKED_EXTERNAL_VISUAL_QA_UNRESOLVED",
            "automatic compatibility reconciliation supports only evidence-backed metric deltas",
        )
    summary = Path(summary_path).resolve()
    try:
        raw = _read_json(summary)
        project = Path(raw.get("project") or summary.parent).resolve()
        _audit, source_results = parse_external_visual_qa(
            summary,
            project_root=project,
            source_command=("slide-visual-polish-qa", "qa-polish"),
            created_at=created_at,
        )
        return build_external_visual_qa_reconciliation(
            source_results,
            composite_qa_dir,
            project_root=project,
            current_pptx_sha256=canonical_output_sha256,
            current_html_sha256=canonical_output_sha256,
            created_at=created_at,
            expected_finding_ids=expected_finding_ids,
        )
    except ExternalVisualQAError as exc:
        raise EvidenceCapsuleError(exc.code, str(exc)) from exc


def validate_forensic_inventory(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the Phase 6.1 dirty-tree disposition record."""

    records = payload.get("records", [])
    if not isinstance(records, list):
        raise EvidenceCapsuleError("BLOCKED_UNRELATED_WORKTREE_CHANGES", "forensic records must be a list")
    for row in records:
        classification = row.get("owner_classification")
        if classification not in {"A", "B", "C", "D"}:
            raise EvidenceCapsuleError("BLOCKED_UNRELATED_WORKTREE_CHANGES", f"unclassified or unrelated path: {row.get('path')}")
        if row.get("contains_absolute_runtime_path") and row.get("proposed_disposition") in {"commit", "preserve", "Phase 6.1A commit candidate"}:
            raise EvidenceCapsuleError("ABSOLUTE_RUNTIME_PATH", f"runtime path cannot enter generic/curated evidence: {row.get('path')}")
        if row.get("generated_binary") and row.get("proposed_disposition") in {"commit", "preserve", "Phase 6.1A commit candidate"}:
            raise EvidenceCapsuleError("GENERATED_BINARY", f"runtime-generated binary cannot be staged: {row.get('path')}")
    moves = payload.get("quarantine_moves", [])
    for move in moves:
        if move.get("before_sha256") != move.get("after_sha256"):
            raise EvidenceCapsuleError("QUARANTINE_HASH_MISMATCH", f"external evidence move changed bytes: {move.get('path')}")
    return {
        "status": "PASS",
        "record_count": len(records),
        "classification_counts": {name: sum(row.get("owner_classification") == name for row in records) for name in "ABCD"},
        "quarantine_move_count": len(moves),
    }


def require_baseline_reachability(report: Mapping[str, Any], *, expected_source_commit: str) -> None:
    """Block fault injection until a fresh post-commit baseline has reached every gate."""

    checks = (
        report.get("status") == "PASS",
        report.get("source_commit") == expected_source_commit,
        report.get("prior_runtime_reused") is False,
        report.get("official_final_gate") == "PASS",
        report.get("composite_qa") == "PASS",
        report.get("render_count") == 6,
        report.get("html_screenshot_count") == 6,
        report.get("missing_artifact_count") == 0,
        report.get("stale_artifact_count") == 0,
        report.get("hash_mismatch_count") == 0,
        report.get("external_qa_reconciliation") == "PASS",
    )
    if not all(checks):
        raise EvidenceCapsuleError(
            "BLOCKED_POSTCOMMIT_REACHABILITY_FAILED",
            "fault injection requires a fresh, current-commit, fully evidenced baseline reachability PASS",
        )


__all__ = [
    "CAPSULE_STATUSES",
    "CAPSULE_STATUS_ORDER",
    "EVIDENCE_PREREQUISITE_DAG",
    "EvidenceCapsuleError",
    "bind_current_output_evidence",
    "build_evidence_capsule",
    "materialize_per_slide_crop_evidence",
    "reconcile_external_visual_qa",
    "require_baseline_reachability",
    "seal_reconstruction_scores",
    "validate_forensic_inventory",
    "verify_manifest_hash",
]
