"""Hash-bound one-slide authoring cache and single-process acceptance gate."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from ..identity import content_sha256
from ..manifest_io import read_json, write_json
from ..schemas import load_schema
from .quality_acceptance import evaluate_visual_quality_acceptance


CACHE_SCHEMA = "codex_one_slide_fast_cache"
CACHE_VERSION = "1.0.0"
DEFAULT_CACHE_NAME = "one_slide_fast_cache.json"
QA_PROFILE_SCHEMA = "slide-visual-polish-qa.calibration-profile.v1"
HTML_CAPTURE_CACHE_CONTRACT = "slide-visual-polish-qa.html-capture-cache.v1"


def probe_one_slide_fast_cache(
    *, project: Path, slide: int, cache_path: Path | None = None
) -> dict[str, Any]:
    """Return a fail-closed cache hit/miss verdict without changing the project."""

    root = project.resolve()
    cache = (cache_path or _default_cache(root, slide)).resolve()
    issues: list[str] = []
    try:
        payload = read_json(cache)
    except (OSError, ValueError, TypeError) as exc:
        return _probe_report(root, slide, cache, [f"cache cannot be read: {exc}"])
    issues.extend(_schema_issues(payload))
    if issues:
        return _probe_report(root, slide, cache, issues)
    if Path(payload["project_root"]).resolve() != root:
        issues.append("cache project_root mismatch")
    if payload["slide"] != slide:
        issues.append("cache slide mismatch")
    if payload["content_hash"] != _content_hash(payload):
        issues.append("cache content_hash mismatch")
    for group in ("inputs", "toolchain", "accepted_evidence"):
        for row in payload[group]:
            path = _resolve_binding(root, row)
            if not path.is_file():
                issues.append(f"{group} artifact is missing: {path}")
            elif _sha256_file(path) != row["sha256"]:
                issues.append(f"{group} artifact hash mismatch: {row['role']}")
    return _probe_report(root, slide, cache, issues, payload.get("cache_key"))


def seal_one_slide_fast_cache(
    *,
    project: Path,
    slide: int,
    pptx: Path,
    html: Path,
    summary: Path,
    qa_profile: Path,
    cache_path: Path | None = None,
) -> dict[str, Any]:
    """Validate current output once and atomically seal the reusable authoring state."""

    if slide <= 0:
        raise ValueError("slide must be a positive integer")
    root = project.resolve()
    pptx_path = pptx.resolve()
    html_path = html.resolve()
    summary_path = summary.resolve()
    qa_profile_path = qa_profile.resolve()
    cache = (cache_path or _default_cache(root, slide)).resolve()

    qa_payload = read_json(qa_profile_path)
    if qa_payload.get("schemaVersion") != QA_PROFILE_SCHEMA:
        raise ValueError(
            "QA profile must be a slide-visual-polish-qa calibration profile; "
            "the design profile is not valid here"
        )
    for group in (
        "knownGoodMetricBands",
        "borderlineMetricBands",
        "knownBadMetricBands",
    ):
        if not isinstance(qa_payload.get(group), dict):
            raise ValueError(f"QA calibration profile lacks {group}")

    _validate_pptx_package(pptx_path)
    if not html_path.is_file() or html_path.stat().st_size == 0:
        raise ValueError(f"HTML output is missing or empty: {html_path}")
    _validate_visual_capture_evidence(
        root=root,
        slide=slide,
        pptx=pptx_path,
        html=html_path,
    )
    quality = evaluate_visual_quality_acceptance(
        project=root, summary_path=summary_path, slides=[slide]
    )
    if not quality["accepted"]:
        raise ValueError("high-fidelity visual QA rejected the slide: " + "; ".join(quality["issues"]))

    inputs = [_binding(root, role, path) for role, path in _input_paths(root, slide)]
    trace_path = root / "out" / "render_trace.json"
    trace = read_json(trace_path)
    _validate_render_trace(trace, slide)
    toolchain = [_external_binding("qa_calibration_profile", qa_profile_path)]
    for role, path in _trace_toolchain_paths(trace):
        toolchain.append(_external_binding(role, path))

    evidence_paths = [
        ("pptx", pptx_path),
        ("html", html_path),
        ("visual_qa_summary", summary_path),
        ("render_trace", trace_path),
        ("native_object_manifest", root / "out" / "native_object_manifest.json"),
        ("crop_coverage_summary", root / "out" / "crop_coverage_summary.json"),
        ("qa_evidence_summary", root / "out" / "qa_evidence_summary.json"),
        ("icon_cache_manifest", root / "assets" / "icons" / "manifest.json"),
        ("background_cache_manifest", root / "assets" / "bg.manifest.json"),
        (
            "pptx_package_validation",
            root / "out" / "pptx_openability_debug" / "pptx_package_validation.json",
        ),
        (
            "visual_metrics",
            root / "work" / f"slide{slide:02d}" / "visual_qa" / "visual_metrics.json",
        ),
        (
            "pptx_raster",
            root / "work" / f"slide{slide:02d}" / "visual_qa" / "pptx_raster.png",
        ),
        (
            "pptx_raster_metadata",
            root / "work" / f"slide{slide:02d}" / "visual_qa" / "pptx_raster_metadata.json",
        ),
        (
            "html_screenshot",
            root / "work" / f"slide{slide:02d}" / "visual_qa" / "html_screenshot.png",
        ),
        (
            "html_screenshot_metadata",
            root / "work" / f"slide{slide:02d}" / "visual_qa" / "html_screenshot_metadata.json",
        ),
    ]
    evidence = [_binding(root, role, path) for role, path in evidence_paths]
    cache_key = content_sha256(
        {
            "slide": slide,
            "inputs": [{"role": row["role"], "sha256": row["sha256"]} for row in inputs],
            "toolchain": [
                {"role": row["role"], "sha256": row["sha256"]}
                for row in toolchain
            ],
        }
    )
    payload: dict[str, Any] = {
        "schema_name": CACHE_SCHEMA,
        "schema_version": CACHE_VERSION,
        "project_root": root.as_posix(),
        "slide": slide,
        "policy": {
            "cache_scope": "authoring_inputs_and_verified_evidence",
            "external_render_and_visual_qa_on_every_final_delivery": True,
            "hardlocks_may_not_be_skipped": True,
            "cache_miss_on_any_hash_change": True,
        },
        "cache_key": cache_key,
        "inputs": inputs,
        "toolchain": toolchain,
        "accepted_evidence": evidence,
        "quality_verdict": quality,
        "content_hash": "0" * 64,
    }
    payload["content_hash"] = _content_hash(payload)
    write_json(cache, payload)
    probe = probe_one_slide_fast_cache(project=root, slide=slide, cache_path=cache)
    if not probe["cache_hit"]:
        raise ValueError("sealed cache failed self-validation: " + "; ".join(probe["issues"]))
    return {"sealed": True, "cache": cache.as_posix(), "cache_key": cache_key, "quality": quality}


def validate_one_slide_fast_cache(
    *, project: Path, slide: int, cache_path: Path | None = None
) -> dict[str, Any]:
    """Single-process final cache, package, trace, and quality validation."""

    root = project.resolve()
    cache = (cache_path or _default_cache(root, slide)).resolve()
    probe = probe_one_slide_fast_cache(project=root, slide=slide, cache_path=cache)
    issues = list(probe["issues"])
    quality: dict[str, Any] | None = None
    if probe["cache_hit"]:
        payload = read_json(cache)
        evidence = {row["role"]: _resolve_binding(root, row) for row in payload["accepted_evidence"]}
        try:
            _validate_pptx_package(evidence["pptx"])
            trace = read_json(evidence["render_trace"])
            _validate_render_trace(trace, slide)
            quality = evaluate_visual_quality_acceptance(
                project=root,
                summary_path=evidence["visual_qa_summary"],
                slides=[slide],
            )
            if not quality["accepted"]:
                issues.extend(quality["issues"])
        except (OSError, ValueError, TypeError, KeyError) as exc:
            issues.append(f"single-process validation failed: {exc}")
    return {
        "valid": not issues,
        "cache_hit": probe["cache_hit"],
        "project": root.as_posix(),
        "slide": slide,
        "cache": cache.as_posix(),
        "quality": quality,
        "issues": issues,
    }


def _input_paths(root: Path, slide: int) -> Iterable[tuple[str, Path]]:
    work = root / "work" / f"slide{slide:02d}"
    required = [
        ("source_png", root / "src" / f"slide{slide}.png"),
        ("slides_js", root / "lib" / "slides.js"),
        ("design_profile", root / "styles" / "active.json"),
        ("deck_crop_plan", root / "work" / "crop_plan.json"),
        ("deck_icon_usage", root / "work" / "icon_usage.json"),
        ("reconstruction_job", work / "reconstruction_job.json"),
        ("measurements", work / "measurements.json"),
        ("vector_usage", work / "vector_usage.json"),
        ("slide_icon_usage", work / "icon_usage.json"),
        ("profile_override", work / "profile_override.json"),
        ("slide_crop_plan", work / "crop_plan.json"),
        ("fragment", work / f"s{slide}.fragment.js"),
        ("reconstruction_score", work / "reconstruction_score.json"),
    ]
    vector_root = work / "vector_preflight"
    vector_files = sorted(path for path in vector_root.rglob("*") if path.is_file())
    if not vector_files:
        raise ValueError(f"vector preflight inputs are missing: {vector_root}")
    yield from required
    for index, path in enumerate(vector_files, start=1):
        yield (f"vector_preflight_{index:03d}", path)


def _validate_render_trace(trace: dict[str, Any], slide: int) -> None:
    if trace.get("invokedByPipeline") is not True or trace.get("strictMode") is not True:
        raise ValueError("render trace does not prove the official strict pipeline")
    for key in ("validation", "finalValidation", "reconstructionValidation"):
        row = trace.get(key)
        if not isinstance(row, dict) or row.get("passed") is not True:
            raise ValueError(f"render trace {key}.passed must be true")
    if slide not in trace.get("reconstructionValidation", {}).get("slidesPassed", []):
        raise ValueError("render trace does not include the requested slide")
    if trace.get("qaSummary", {}).get("passed") is not True:
        raise ValueError("render trace qaSummary.passed must be true")
    if trace.get("enforcementDisabled") is True:
        raise ValueError("render trace shows enforcement disabled")


def _trace_toolchain_paths(trace: dict[str, Any]) -> Iterable[tuple[str, Path]]:
    fields = {
        "renderer_build": "buildJsPath",
        "renderer_slides": "slidesJsPath",
        "renderer_kit": "kitJsPath",
        "renderer_atoms_pptx": "atomsPptxPath",
        "renderer_atoms_html": "atomsHtmlPath",
    }
    for role, field in fields.items():
        raw = trace.get(field)
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"render trace lacks {field}")
        yield role, Path(raw).resolve()


def _validate_pptx_package(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"PPTX output is missing: {path}")
    required = {"[Content_Types].xml", "_rels/.rels", "ppt/presentation.xml"}
    try:
        with zipfile.ZipFile(path) as package:
            names = set(package.namelist())
            missing = sorted(required - names)
            if missing:
                raise ValueError(f"PPTX package is missing {missing}")
            corrupt = package.testzip()
            if corrupt:
                raise ValueError(f"PPTX package has corrupt member {corrupt}")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"PPTX output is not a valid ZIP package: {path}") from exc


def _validate_visual_capture_evidence(
    *, root: Path, slide: int, pptx: Path, html: Path
) -> None:
    visual = root / "work" / f"slide{slide:02d}" / "visual_qa"
    pptx_raster = visual / "pptx_raster.png"
    html_screenshot = visual / "html_screenshot.png"
    pptx_metadata = read_json(visual / "pptx_raster_metadata.json")
    html_metadata = read_json(visual / "html_screenshot_metadata.json")

    for label, path in (
        ("PPTX raster", pptx_raster),
        ("HTML screenshot", html_screenshot),
    ):
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"{label} is missing or empty: {path}")

    if html_metadata.get("captureCacheContract") != HTML_CAPTURE_CACHE_CONTRACT:
        raise ValueError("HTML screenshot metadata lacks the hash-bound capture cache contract")
    if not isinstance(html_metadata.get("cacheHit"), bool):
        raise ValueError("HTML screenshot metadata must record cacheHit as a boolean")
    if html_metadata.get("qaStaticModeUsed") is not True:
        raise ValueError("HTML screenshot metadata lacks qa-static evidence")
    if html_metadata.get("modifiedHtml") is not False:
        raise ValueError("HTML screenshot metadata must prove modifiedHtml=false")
    if html_metadata.get("deviceScaleFactor") != 1:
        raise ValueError("HTML screenshot metadata must use deviceScaleFactor=1")
    if html_metadata.get("dimensionCheck") != "exact":
        raise ValueError("HTML screenshot metadata must prove exact dimensions")
    if html_metadata.get("expectedScreenshotDimensions") != html_metadata.get(
        "actualScreenshotDimensions"
    ):
        raise ValueError("HTML screenshot expected and actual dimensions differ")
    _validate_metadata_binding(
        metadata=html_metadata,
        artifact=html,
        artifact_path_key="html",
        artifact_hash_key="htmlSha256",
        output=html_screenshot,
        label="HTML screenshot",
        slide=slide,
    )

    if pptx_metadata.get("modifiedPptx") is not False:
        raise ValueError("PPTX raster metadata must prove modifiedPptx=false")
    _validate_metadata_binding(
        metadata=pptx_metadata,
        artifact=pptx,
        artifact_path_key="pptx",
        artifact_hash_key="pptxSha256",
        output=pptx_raster,
        label="PPTX raster",
        slide=slide,
    )


def _validate_metadata_binding(
    *,
    metadata: dict[str, Any],
    artifact: Path,
    artifact_path_key: str,
    artifact_hash_key: str,
    output: Path,
    label: str,
    slide: int,
) -> None:
    if metadata.get("sourceSlideId") != slide:
        raise ValueError(f"{label} metadata sourceSlideId mismatch")
    if Path(str(metadata.get(artifact_path_key, ""))).resolve() != artifact.resolve():
        raise ValueError(f"{label} metadata artifact path mismatch")
    if metadata.get(artifact_hash_key) != _sha256_file(artifact):
        raise ValueError(f"{label} metadata artifact hash mismatch")
    if Path(str(metadata.get("output", ""))).resolve() != output.resolve():
        raise ValueError(f"{label} metadata output path mismatch")
    if metadata.get("outputSha256") != _sha256_file(output):
        raise ValueError(f"{label} metadata output hash mismatch")


def _binding(root: Path, role: str, path: Path) -> dict[str, str]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"required artifact is missing: {resolved}")
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError:
        return _external_binding(role, resolved)
    return {"role": role, "path": relative, "path_scope": "project", "sha256": _sha256_file(resolved)}


def _external_binding(role: str, path: Path) -> dict[str, str]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"required external artifact is missing: {resolved}")
    return {"role": role, "path": resolved.as_posix(), "path_scope": "absolute", "sha256": _sha256_file(resolved)}


def _resolve_binding(root: Path, row: dict[str, Any]) -> Path:
    if row["path_scope"] == "project":
        candidate = (root / row["path"]).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"project binding escapes project root: {row['path']}") from exc
        return candidate
    return Path(row["path"]).resolve()


def _default_cache(root: Path, slide: int) -> Path:
    return root / "work" / f"slide{slide:02d}" / DEFAULT_CACHE_NAME


def _schema_issues(payload: dict[str, Any]) -> list[str]:
    # This schema has only local refs. Loading the repository-wide registry here
    # adds a large cold-start penalty without strengthening validation.
    validator = Draft202012Validator(load_schema(CACHE_SCHEMA))
    return [
        f"cache schema:{'.'.join(str(part) for part in issue.path) or '$'}: {issue.message}"
        for issue in sorted(
            validator.iter_errors(payload),
            key=lambda item: list(item.path),
        )
    ]


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


def _probe_report(
    root: Path,
    slide: int,
    cache: Path,
    issues: list[str],
    cache_key: str | None = None,
) -> dict[str, Any]:
    return {
        "cache_hit": not issues,
        "project": root.as_posix(),
        "slide": slide,
        "cache": cache.as_posix(),
        "cache_key": cache_key,
        "issues": issues,
    }


__all__ = [
    "CACHE_SCHEMA",
    "CACHE_VERSION",
    "probe_one_slide_fast_cache",
    "seal_one_slide_fast_cache",
    "validate_one_slide_fast_cache",
]
