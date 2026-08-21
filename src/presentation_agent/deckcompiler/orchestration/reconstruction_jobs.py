"""Prepare and validate isolated high-fidelity PNG-to-PPTX slide jobs."""

from __future__ import annotations

import hashlib
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import DeckCompilerError
from ..identity import content_sha256, stable_id
from ..manifest_io import read_json, write_json
from .image_requests import REQUEST_MANIFEST_NAME, validate_image_request_bundle
from .skillset_plan import validate_skillset_execution_plan
from .vector_preflight import (
    MANIFEST_NAME as VECTOR_PREFLIGHT_MANIFEST_NAME,
    POLICY_ID as VECTOR_PREFLIGHT_POLICY_ID,
    slide_preflight_path,
    validate_vector_preflight_bundle,
    validate_vector_preflight_slide_bundle,
)


PROJECT_DIRECTORY = "pngtopptx-project"
JOB_MANIFEST_NAME = "reconstruction_job_manifest.json"
JOB_MANIFEST_SCHEMA = "codex_reconstruction_job_manifest"
JOB_SCHEMA = "codex_slide_reconstruction_job"
MAX_PARALLEL_WORKERS = 6
AUTHORING_OUTPUT_NAMES = (
    "measurements.json",
    "vector_usage.json",
    "icon_usage.json",
    "profile_override.json",
    "crop_plan.json",
    "s{slide}.fragment.js",
    "reconstruction_notes.md",
    "editability_inventory.md",
)
POST_RENDER_OUTPUT_NAMES = (
    "reconstruction_score.json",
    "qa_report.md",
    "qa_result.json",
    "qa_evidence.json",
    "worker_receipt.json",
)
REQUIRED_OUTPUT_NAMES = AUTHORING_OUTPUT_NAMES + POST_RENDER_OUTPUT_NAMES


@dataclass(frozen=True, slots=True)
class ReconstructionJobPreparationResult:
    workflow_id: str
    runtime_root: Path
    manifest_path: Path
    job_paths: tuple[Path, ...]
    worker_prompt_paths: tuple[Path, ...]
    slide_count: int


@dataclass(frozen=True, slots=True)
class ReconstructionSlideJobPreparationResult:
    workflow_id: str
    runtime_root: Path
    slide_number: int
    job_path: Path
    worker_prompt_path: Path


def prepare_reconstruction_jobs(
    runtime_root: Path,
) -> ReconstructionJobPreparationResult:
    """Write one hash-bound, fresh-context reconstruction job per source PNG."""

    root = runtime_root.resolve()
    bundle = _expected_bundle(root)
    job_paths: list[Path] = []
    prompt_paths: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for row in bundle["jobs"]:
        work_dir = root / row["work_dir"]
        work_dir.mkdir(parents=True, exist_ok=True)
        job_path = write_json(work_dir / "reconstruction_job.json", row["job"])
        prompt_path = work_dir / "worker_prompt.md"
        prompt_path.write_text(row["worker_prompt"], encoding="utf-8", newline="\n")
        job_paths.append(job_path)
        prompt_paths.append(prompt_path)
        manifest_rows.append(
            {
                **row["lineage"],
                "job": _artifact(root, job_path),
                "worker_prompt": _artifact(root, prompt_path),
            }
        )

    manifest = {
        **bundle["header"],
        "jobs": manifest_rows,
    }
    manifest["content_hash"] = content_sha256(manifest)
    manifest_path = write_json(
        root / PROJECT_DIRECTORY / "work" / JOB_MANIFEST_NAME,
        manifest,
    )
    report = validate_reconstruction_job_bundle(root)
    if not report["valid"]:
        raise _error(
            "DC_RECONSTRUCTION_JOB_PREPARATION_INVALID",
            "; ".join(report["issues"][:8]),
            manifest_path,
        )
    return ReconstructionJobPreparationResult(
        workflow_id=bundle["header"]["workflow_id"],
        runtime_root=root,
        manifest_path=manifest_path,
        job_paths=tuple(job_paths),
        worker_prompt_paths=tuple(prompt_paths),
        slide_count=len(job_paths),
    )


def prepare_reconstruction_job(
    runtime_root: Path,
    *,
    slide_number: int,
    accepted_call: dict[str, Any],
) -> ReconstructionSlideJobPreparationResult:
    """Prepare one slide immediately, without waiting for the batch barrier."""

    root = runtime_root.resolve()
    row = _expected_incremental_job(root, slide_number, accepted_call)
    work_dir = root / row["work_dir"]
    work_dir.mkdir(parents=True, exist_ok=True)
    job_path = write_json(work_dir / "reconstruction_job.json", row["job"])
    prompt_path = work_dir / "worker_prompt.md"
    prompt_path.write_text(row["worker_prompt"], encoding="utf-8", newline="\n")
    return ReconstructionSlideJobPreparationResult(
        workflow_id=row["job"]["workflow_id"],
        runtime_root=root,
        slide_number=slide_number,
        job_path=job_path,
        worker_prompt_path=prompt_path,
    )


def validate_reconstruction_job_bundle(
    runtime_root: Path,
    *,
    require_authoring_outputs: bool = False,
    require_worker_outputs: bool = False,
    require_integrated_outputs: bool = False,
) -> dict[str, Any]:
    """Reject stale jobs, cross-slide context, shared writes, or incomplete workers."""

    root = runtime_root.resolve()
    manifest_path = root / PROJECT_DIRECTORY / "work" / JOB_MANIFEST_NAME
    issues: list[str] = []
    try:
        expected = _expected_bundle(root)
        manifest = read_json(manifest_path)
    except (DeckCompilerError, OSError, ValueError, TypeError) as exc:
        message = exc.message if isinstance(exc, DeckCompilerError) else str(exc)
        return {
            "valid": False,
            "workflow_id": None,
            "slide_count": 0,
            "authoring_outputs_required": require_authoring_outputs,
            "worker_outputs_required": require_worker_outputs,
            "integrated_outputs_required": require_integrated_outputs,
            "issues": [message],
        }

    expected_header = expected["header"]
    for key, value in expected_header.items():
        if manifest.get(key) != value:
            issues.append(f"reconstruction job manifest {key} must be {value!r}")
    rows = manifest.get("jobs")
    if not isinstance(rows, list) or len(rows) != len(expected["jobs"]):
        issues.append(
            "reconstruction job manifest jobs must contain exactly "
            f"{len(expected['jobs'])} rows"
        )
        rows = []

    for index, expected_row in enumerate(expected["jobs"]):
        if index >= len(rows):
            break
        actual_row = rows[index]
        slide = expected_row["lineage"]["slide_number"]
        label = f"reconstruction job slide {slide}"
        if not isinstance(actual_row, dict):
            issues.append(f"{label} manifest row must be an object")
            continue
        for key, value in expected_row["lineage"].items():
            if actual_row.get(key) != value:
                issues.append(f"{label} {key} does not match selected ImageGen output")
        for artifact_key, expected_value in (
            ("job", expected_row["job"]),
            ("worker_prompt", expected_row["worker_prompt"]),
        ):
            artifact = actual_row.get(artifact_key)
            if not isinstance(artifact, dict):
                issues.append(f"{label} {artifact_key} artifact is missing")
                continue
            path = _resolve_inside(
                root, artifact.get("path"), f"{label} {artifact_key}"
            )
            if path is None or not path.is_file():
                issues.append(f"{label} {artifact_key} file is missing")
                continue
            actual_sha = _sha256_file(path)
            if artifact.get("sha256") != actual_sha:
                issues.append(f"{label} {artifact_key} sha256 mismatch")
            if artifact_key == "job":
                try:
                    actual_value = read_json(path)
                except (OSError, ValueError, TypeError) as exc:
                    issues.append(f"{label} job is invalid JSON: {exc}")
                    continue
            else:
                try:
                    actual_value = path.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    issues.append(f"{label} worker prompt is invalid UTF-8: {exc}")
                    continue
            if actual_value != expected_value:
                issues.append(
                    f"{label} {artifact_key} was not deterministically derived from "
                    "the approved request and selected source PNG"
                )
        if require_worker_outputs:
            job_path = root / expected_row["work_dir"] / "reconstruction_job.json"
            _validate_worker_outputs(root, job_path, expected_row["job"], issues)
        elif require_authoring_outputs:
            job_path = root / expected_row["work_dir"] / "reconstruction_job.json"
            _validate_authoring_outputs(root, job_path, expected_row["job"], issues)

    if require_integrated_outputs:
        _validate_integrated_outputs(root, expected["jobs"], issues)

    expected_hash = content_sha256(
        {key: value for key, value in manifest.items() if key != "content_hash"}
    )
    if manifest.get("content_hash") != expected_hash:
        issues.append("reconstruction job manifest content_hash mismatch")

    return {
        "valid": not issues,
        "workflow_id": expected_header["workflow_id"],
        "slide_count": len(expected["jobs"]),
        "authoring_outputs_required": require_authoring_outputs,
        "worker_outputs_required": require_worker_outputs,
        "integrated_outputs_required": require_integrated_outputs,
        "issues": issues,
    }


def _expected_bundle(root: Path) -> dict[str, Any]:
    context = _load_job_context(root)
    request_path = context["request_path"]
    request_manifest = context["request_manifest"]
    workflow_id = context["workflow_id"]
    plan_path = context["plan_path"]
    renderer = context["renderer"]
    execution_profile = context["execution_profile"]
    batch_path = root / "image_batches" / "image_generation_batch_manifest.json"
    batch = read_json(batch_path)
    calls = _accepted_calls(batch, len(request_manifest["slides"]))
    jobs = [
        _build_job_row(
            root,
            workflow_id=workflow_id,
            request_row=request_row,
            call=calls[int(request_row["slide_number"])],
            renderer=renderer,
            execution_profile=execution_profile,
            vector_preflight_path=slide_preflight_path(
                root, int(request_row["slide_number"])
            ),
            vector_preflight=read_json(
                slide_preflight_path(root, int(request_row["slide_number"]))
            ),
            vector_row=context["vector_by_slide"][int(request_row["slide_number"])],
            lineage_path=batch_path,
        )
        for request_row in request_manifest["slides"]
    ]

    header = {
        "schema_name": JOB_MANIFEST_SCHEMA,
        "schema_version": "1.1.0",
        "workflow_id": workflow_id,
        "context_unit": "one_source_slide_per_fresh_context",
        "dispatch_mode": "bounded_parallel_workers",
        "max_parallel_workers": min(
            int(execution_profile["max_reconstruction_workers"]), len(jobs)
        ),
        "shared_file_writer": "integrator_only",
        "worker_model": execution_profile["target_model"],
        "worker_reasoning_effort": execution_profile[
            "target_reasoning_effort"
        ],
        "token_policy": "compact_job_plus_one_source_slide_no_full_deck_duplication",
        "qa_execution": {
            "authoring_before_integration": True,
            "isolated_one_slide_builds_required": False,
            "shared_full_deck_render_passes": 2,
            "source_mapped_per_slide_qa_required": True,
            "final_full_deck_gate_required": True,
        },
        "source_artifacts": {
            "image_request_manifest": _artifact(root, request_path),
            "image_generation_batch_manifest": _artifact(root, batch_path),
            "skillset_execution_plan": _artifact(root, plan_path),
            "vector_preflight_manifest": _artifact(
                root, context["vector_preflight_path"]
            ),
        },
        "slide_count": len(jobs),
    }
    return {"header": header, "jobs": jobs}


def _expected_incremental_job(
    root: Path,
    slide_number: int,
    accepted_call: dict[str, Any],
) -> dict[str, Any]:
    context = _load_job_context(root, slide_number=slide_number)
    request_manifest = context["request_manifest"]
    request_row = next(
        (
            row
            for row in request_manifest["slides"]
            if int(row["slide_number"]) == slide_number
        ),
        None,
    )
    if request_row is None:
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            f"image request manifest has no slide {slide_number}",
            context["request_path"],
        )
    return _build_job_row(
        root,
        workflow_id=context["workflow_id"],
        request_row=request_row,
        call=accepted_call,
        renderer=context["renderer"],
        execution_profile=context["execution_profile"],
        vector_preflight_path=context["vector_preflight_path"],
        vector_preflight=context["vector_preflight"],
        vector_row=context["vector_by_slide"][slide_number],
        lineage_path=(
            root / "image_batches" / "accepted" / f"slide-{slide_number:03d}.json"
        ),
    )


def _load_job_context(
    root: Path,
    *,
    slide_number: int | None = None,
) -> dict[str, Any]:
    request_path = root / "image_requests" / REQUEST_MANIFEST_NAME
    request_report = validate_image_request_bundle(root, request_path)
    if not request_report["valid"]:
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            "Image request lineage is invalid: "
            + "; ".join(request_report["issues"][:6]),
            request_path,
        )
    request_manifest = read_json(request_path)
    workflow_id = str(request_manifest.get("workflow_id", "")).strip()
    plan_path = root / "skillset_execution_plan.json"
    plan = read_json(plan_path)
    plan_issues = validate_skillset_execution_plan(
        plan_path,
        expected_workflow_id=workflow_id,
    )
    if plan_issues:
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            "skillset execution plan is invalid: " + "; ".join(plan_issues[:6]),
            plan_path,
        )
    renderer = next(
        (
            row
            for row in plan.get("ordered_skills", [])
            if isinstance(row, dict)
            and row.get("skill_name") == "slide-image-dual-render"
        ),
        None,
    )
    if not isinstance(renderer, dict):
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            "skillset execution plan is missing slide-image-dual-render",
            plan_path,
        )
    vector_preflight_path = (
        slide_preflight_path(root, slide_number)
        if slide_number is not None
        else root / PROJECT_DIRECTORY / "work" / VECTOR_PREFLIGHT_MANIFEST_NAME
    )
    vector_report = (
        validate_vector_preflight_slide_bundle(root, slide_number)
        if slide_number is not None
        else validate_vector_preflight_bundle(root)
    )
    if not vector_report["valid"]:
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            "PNG-to-SVG vector preflight is invalid: "
            + "; ".join(vector_report["issues"][:6]),
            vector_preflight_path,
        )
    vector_preflight = read_json(vector_preflight_path)
    vector_by_slide = (
        {int(vector_preflight["slide"]["slide_number"]): vector_preflight["slide"]}
        if slide_number is not None
        else {
            int(row["slide_number"]): row for row in vector_preflight["slides"]
        }
    )
    expected_slides = (
        {slide_number}
        if slide_number is not None
        else {int(row["slide_number"]) for row in request_manifest["slides"]}
    )
    if set(vector_by_slide) != expected_slides:
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            "vector preflight slide coverage does not match image requests",
            vector_preflight_path,
        )
    return {
        "request_path": request_path,
        "request_manifest": request_manifest,
        "workflow_id": workflow_id,
        "plan_path": plan_path,
        "renderer": renderer,
        "execution_profile": plan["execution_profile"],
        "vector_preflight_path": vector_preflight_path,
        "vector_preflight": vector_preflight,
        "vector_by_slide": vector_by_slide,
    }


def _build_job_row(
    root: Path,
    *,
    workflow_id: str,
    request_row: dict[str, Any],
    call: dict[str, Any],
    renderer: dict[str, Any],
    execution_profile: dict[str, Any],
    vector_preflight_path: Path,
    vector_preflight: dict[str, Any],
    vector_row: dict[str, Any],
    lineage_path: Path,
) -> dict[str, Any]:
    slide = int(request_row["slide_number"])
    if call.get("status") != "ACCEPTED":
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            f"slide {slide} image call must be ACCEPTED",
            lineage_path,
        )
    prompt_path = _required_artifact_path(root, request_row.get("prompt"), "prompt")
    sidecar_path = _required_artifact_path(
        root, request_row.get("semantic_sidecar"), "semantic sidecar"
    )
    project = root / PROJECT_DIRECTORY
    source_path = project / "src" / f"slide{slide}.png"
    width, height = _png_dimensions(source_path)
    prompt_sha = _sha256_file(prompt_path)
    sidecar_sha = _sha256_file(sidecar_path)
    source_sha = _sha256_file(source_path)
    if call.get("request_id") != request_row.get("request_id"):
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            f"slide {slide} image call request_id mismatch",
            lineage_path,
        )
    if call.get("prompt_sha256") != prompt_sha:
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            f"slide {slide} image call prompt_sha256 mismatch",
            lineage_path,
        )
    if call.get("selected_png_sha256") != source_sha:
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            f"slide {slide} selected_png_sha256 mismatch",
            lineage_path,
        )
    job_id = stable_id(
        "reconstructionjob",
        workflow_id,
        request_row["request_id"],
        source_sha,
        sidecar_sha,
        vector_row["slide_content_hash"],
    )
    work_dir = project / "work" / f"slide{slide:02d}"
    authoring_outputs = [
        name.format(slide=slide) for name in AUTHORING_OUTPUT_NAMES
    ]
    post_render_outputs = [
        name.format(slide=slide) for name in POST_RENDER_OUTPUT_NAMES
    ]
    job: dict[str, Any] = {
        "schema_name": JOB_SCHEMA,
        "schema_version": "1.1.0",
        "workflow_id": workflow_id,
        "job_id": job_id,
        "slide_number": slide,
        "slide_id": request_row["slide_id"],
        "source_png": {
            **_artifact(root, source_path),
            "width": width,
            "height": height,
        },
        "image_request": _artifact(root, prompt_path),
        "semantic_sidecar": _artifact(root, sidecar_path),
        "vector_preflight": {
            "policy_id": VECTOR_PREFLIGHT_POLICY_ID,
            "manifest": _artifact(root, vector_preflight_path),
            "slide_content_hash": vector_row["slide_content_hash"],
            "measurement_inventory": vector_row["measurement_inventory"],
            "detector_record": vector_row["detector_record"],
            "regions": vector_row["regions"],
            "parametric_icon_library": vector_preflight[
                "pipeline_provenance"
            ]["svg_icon_library"],
            "available_parametric_icon_names": vector_preflight[
                "pipeline_provenance"
            ]["svg_icon_names"],
        },
        "request_lineage": {
            key: request_row[key]
            for key in (
                "request_id",
                "blueprint_entry_sha256",
                "visual_route_id",
                "visual_route_sha256",
                "layout_id",
                "layout_sha256",
            )
        },
        "context_policy": {
            "fresh_context_required": True,
            "allowed_source_slides": [slide],
            "full_deck_context_forbidden": True,
            "shared_file_writes_forbidden": True,
        },
        "execution_profile": {
            key: execution_profile[key]
            for key in (
                "profile_name",
                "target_model",
                "target_reasoning_effort",
                "fallback_policy",
                "determinism_contract",
                "worker_context",
            )
        },
        "authoring_contract": {
            "renderer_skill": "slide-image-dual-render",
            "renderer_skill_path": renderer["skill_path"],
            "quality": "reconstruction",
            "targets": ["pptx", "html"],
            "source_image_role": "visual_fidelity_target_not_delivered_slide_surface",
            "exact_text_source": "semantic_sidecar",
            "measured_geometry_source": "vector_preflight.measurement_inventory",
            "measured_coordinates_authoritative": True,
            "bounded_svg_assets_preferred_when_gate_passed": True,
            "semantic_text_vectorization_forbidden": True,
            "full_slide_vectorization_forbidden": True,
            "native_text_required": True,
            "native_structure_required": True,
            "selective_photoreal_crops_allowed": True,
            "full_slide_raster_forbidden": True,
            "backend_branching_forbidden": True,
        },
        "execution_phases": {
            "authoring": "complete_before_integration",
            "visual_qa": "after_shared_full_deck_preview_render",
            "final_acceptance": "after_final_full_deck_reconstruction_gate",
        },
        "authoring_outputs": authoring_outputs,
        "post_render_outputs": post_render_outputs,
        "required_outputs": authoring_outputs + post_render_outputs,
        "receipt_binding": {
            "job_id": job_id,
            "source_png_sha256": source_sha,
            "image_request_sha256": prompt_sha,
            "semantic_sidecar_sha256": sidecar_sha,
            "vector_preflight_sha256": _sha256_file(vector_preflight_path),
            "vector_slide_content_hash": vector_row["slide_content_hash"],
            "artifact_hashes_required": True,
        },
        "content_hash": "0" * 64,
    }
    job["content_hash"] = content_sha256(
        {key: value for key, value in job.items() if key != "content_hash"}
    )
    return {
        "work_dir": work_dir.relative_to(root).as_posix(),
        "lineage": {
            "slide_number": slide,
            "slide_id": request_row["slide_id"],
            "job_id": job_id,
            "request_id": request_row["request_id"],
            "source_png_sha256": source_sha,
            "vector_slide_content_hash": vector_row["slide_content_hash"],
            "job_content_hash": job["content_hash"],
        },
        "job": job,
        "worker_prompt": _worker_prompt(root, work_dir, job),
    }


def _worker_prompt(root: Path, work_dir: Path, job: dict[str, Any]) -> str:
    slide = job["slide_number"]
    profile = job["execution_profile"]
    authoring = "\n".join(f"- `{name}`" for name in job["authoring_outputs"])
    post_render = "\n".join(f"- `{name}`" for name in job["post_render_outputs"])
    return f"""Use `$slide-image-dual-render` for exactly slide {slide}.

Execution profile: `{profile['profile_name']}` = model
`{profile['target_model']}` with reasoning effort
`{profile['target_reasoning_effort']}`. Do not silently substitute another
model or effort. The profile changes worker routing only; the bound prompt,
Semantic Sidecar, renderer contract, vector policy, compiler, and QA are fixed.
Any configured fallback is failed-slide-only and may run only after an explicit
contract or blocking-quality failure.

Launch this fresh worker with the exact `worker_context.codex_argv` stored in
the job. Do not load the global plugin/Skill catalog. The renderer Skill path
below is the only Skill instruction path required for this job.

This is one isolated fresh-context reconstruction job. Read
`{(work_dir / "reconstruction_job.json").as_posix()}` first and inspect only the
source image and semantic sidecar named there. Do not load any other slide image
or full-deck prompt into this context.

Treat `vector_preflight.measurement_inventory` as authoritative geometry. Do
not spend model tokens re-measuring detected regions. Use each passed
`bounded_svg_asset` directly when it preserves the intended editable structure;
record every used or deliberately deferred measured region in
`vector_usage.json`. The hash-bound raw `parametric_icon_library` may replace a
measured simple icon only when one of its declared names is an exact semantic
match; record that decision in `parametricIconUses`. Never convert semantic
text, a continuous-tone region, or the complete slide to SVG. The measured
assets are inputs to the official SkillSet reconstruction, not an alternate
renderer.

Write every renderer icon requested by the fragment to `icon_usage.json` using
schemaVersion `slide-image-dual-render.icon-usage.v1` and explicit
`{{"concept": "...", "color": "..."}}` pairs. Include an empty `icons` array
when the fragment uses no renderer icons. This manifest is the sole authority
for on-demand icon generation; do not request the full icon catalog.

Quality target: reproduce the source slide's composition, typography hierarchy,
spacing, visual density, imagery, and meaningful small details at the level of a
careful one-slide SkillSet conversion. Rebuild all readable text and structural
elements as editable native PPTX/HTML objects. Use raster crops only for genuine
photographic, continuous-tone, or 3D regions; never use the source PNG or a
near-full-slide crop as the delivered slide surface. Preserve exact copy from the
semantic sidecar. Do not simplify the source into generic cards or an invented
template.

Read the renderer Skill, `styles/_schema.md`, `scripts/classify.md`,
`references/codex-subagents.md`, and `references/hardlock-mode.md`. Populate the
required measurements from the authoritative inventory and classify before
authoring; measure pixels again only when the inventory explicitly leaves a
region unresolved. Write only inside `{work_dir.as_posix()}`; never edit
`lib/slides.js`, `styles/`, `assets/`, build scripts, or other slide folders.
If a deliberately sparse title slide needs the canonical native-text threshold
exception, or an image-led slide needs the canonical total-crop exception, record
it in `profile_override.json.exceptions` with a specific `reason`; do not invent
exceptions to bypass visual fidelity, editability, largest-crop, text/table-crop,
or dense-infographic limits.
The integrator alone will merge accepted fragments into shared files. Complete
the authoring outputs below as soon as this job arrives, then stop. Do not run an
isolated one-slide PPTX/HTML build: the workflow renders the integrated deck and
reuses its source-mapped slide pages for per-slide PPTX and HTML QA, avoiding
twenty duplicate builds without relaxing fidelity or editability checks.

Authoring outputs required before integration:
{authoring}

Post-render outputs required only after shared preview evidence exists:
{post_render}

After the shared preview comparison passes, `worker_receipt.json` must use
`agent: slide_reconstruct_worker`,
`status: completed`, `sharedFilesEdited: false`, list every produced artifact,
and include `jobId`, `jobContentHash`, all five receipt-binding hashes from the
job, plus `artifactHashes` containing the SHA-256 of every listed artifact other
than the receipt itself. Do not report pass until the source-mapped shared-render
comparison and editable-object checks have actually passed.
"""


def _validate_authoring_outputs(
    root: Path,
    job_path: Path,
    job: dict[str, Any],
    issues: list[str],
) -> None:
    slide = int(job["slide_number"])
    work_dir = job_path.parent
    label = f"slide {slide} authoring worker"
    required = list(job.get("authoring_outputs", []))
    if required != [name.format(slide=slide) for name in AUTHORING_OUTPUT_NAMES]:
        issues.append(f"{label} authoring output contract is invalid")
        return
    for name in required:
        if not (work_dir / name).is_file():
            issues.append(f"{label} is missing {name}")
    if any(not (work_dir / name).is_file() for name in required):
        return

    measurements = _read_worker_json(work_dir / "measurements.json", issues, label)
    if measurements is not None:
        canvas = measurements.get("canvas", measurements)
        if not isinstance(canvas, dict):
            issues.append(f"{label} measurements.json canvas must be an object")
        else:
            if _number(canvas.get("width")) != job["source_png"]["width"]:
                issues.append(f"{label} measurements canvas width mismatch")
            if _number(canvas.get("height")) != job["source_png"]["height"]:
                issues.append(f"{label} measurements canvas height mismatch")

    vector_usage = _read_worker_json(work_dir / "vector_usage.json", issues, label)
    if vector_usage is not None:
        _validate_vector_usage(vector_usage, job, label, issues)

    profile = _read_worker_json(work_dir / "profile_override.json", issues, label)
    if profile is not None:
        if not any(
            str(profile.get(key, "")).strip() for key in ("profileId", "profile", "id")
        ):
            issues.append(f"{label} profile_override.json requires profileId")
        if not str(profile.get("confidence", "")).strip():
            issues.append(f"{label} profile_override.json requires confidence")

    crop_plan = _read_worker_json(work_dir / "crop_plan.json", issues, label)
    if crop_plan is not None:
        _validate_crops(crop_plan, slide, job["source_png"], issues)

    fragment_path = work_dir / f"s{slide}.fragment.js"
    try:
        fragment = fragment_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        issues.append(f"{label} fragment is not valid UTF-8: {exc}")
    else:
        functions = re.findall(
            r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(\s*s\s*\)", fragment
        )
        if functions != [f"s{slide}"]:
            issues.append(
                f"{label} fragment expected exactly one function s{slide}(s), got {functions}"
            )
        lowered = fragment.lower()
        if "require(" in lowered or "require (" in lowered:
            issues.append(f"{label} fragment must use the shared kit without require(...)")
        if f"slide{slide}.png" in lowered:
            issues.append(f"{label} fragment references the full source PNG")

    for markdown_name in ("reconstruction_notes.md", "editability_inventory.md"):
        try:
            value = (work_dir / markdown_name).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            issues.append(f"{label} {markdown_name} is not valid UTF-8: {exc}")
            continue
        if len(value.strip()) < 20:
            issues.append(f"{label} {markdown_name} is too short to be evidence")


def _validate_worker_outputs(
    root: Path,
    job_path: Path,
    job: dict[str, Any],
    issues: list[str],
) -> None:
    slide = int(job["slide_number"])
    work_dir = job_path.parent
    label = f"slide {slide} worker"
    required = list(job["required_outputs"])
    for name in required:
        if not (work_dir / name).is_file():
            issues.append(f"{label} is missing {name}")
    if any(not (work_dir / name).is_file() for name in required):
        return

    measurements = _read_worker_json(work_dir / "measurements.json", issues, label)
    if measurements is not None:
        canvas = measurements.get("canvas", measurements)
        if not isinstance(canvas, dict):
            issues.append(f"{label} measurements.json canvas must be an object")
        else:
            expected_width = job["source_png"]["width"]
            expected_height = job["source_png"]["height"]
            if _number(canvas.get("width")) != expected_width:
                issues.append(
                    f"{label} measurements canvas width must be {expected_width}"
                )
            if _number(canvas.get("height")) != expected_height:
                issues.append(
                    f"{label} measurements canvas height must be {expected_height}"
                )

    vector_usage = _read_worker_json(work_dir / "vector_usage.json", issues, label)
    if vector_usage is not None:
        _validate_vector_usage(vector_usage, job, label, issues)

    icon_usage = _read_worker_json(work_dir / "icon_usage.json", issues, label)
    if icon_usage is not None:
        if icon_usage.get("schemaVersion") != "slide-image-dual-render.icon-usage.v1":
            issues.append(
                f"{label} icon_usage.schemaVersion must be "
                "slide-image-dual-render.icon-usage.v1"
            )
        icons = icon_usage.get("icons")
        if not isinstance(icons, list):
            issues.append(f"{label} icon_usage.icons must be an array")
        else:
            seen: set[tuple[str, str]] = set()
            for index, item in enumerate(icons):
                if not isinstance(item, dict):
                    issues.append(f"{label} icon_usage.icons[{index}] must be an object")
                    continue
                concept = str(item.get("concept", "")).strip()
                color = str(item.get("color", "")).strip()
                if not re.fullmatch(r"[a-z][a-z0-9]*", concept):
                    issues.append(
                        f"{label} icon_usage.icons[{index}].concept is invalid"
                    )
                if color not in {
                    "white",
                    "lblue",
                    "cyan",
                    "red",
                    "green",
                    "gold",
                    "blue",
                }:
                    issues.append(
                        f"{label} icon_usage.icons[{index}].color is invalid"
                    )
                pair = (concept, color)
                if pair in seen:
                    issues.append(
                        f"{label} icon_usage contains duplicate pair {concept}:{color}"
                    )
                seen.add(pair)

    profile = _read_worker_json(work_dir / "profile_override.json", issues, label)
    if profile is not None:
        if not any(
            str(profile.get(key, "")).strip() for key in ("profileId", "profile", "id")
        ):
            issues.append(f"{label} profile_override.json requires profileId")
        if not str(profile.get("confidence", "")).strip():
            issues.append(f"{label} profile_override.json requires confidence")

    crop_plan = _read_worker_json(work_dir / "crop_plan.json", issues, label)
    if crop_plan is not None:
        _validate_crops(crop_plan, slide, job["source_png"], issues)

    fragment_path = work_dir / f"s{slide}.fragment.js"
    try:
        fragment = fragment_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        issues.append(f"{label} fragment is not valid UTF-8: {exc}")
    else:
        functions = re.findall(
            r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(\s*s\s*\)", fragment
        )
        if functions != [f"s{slide}"]:
            issues.append(
                f"{label} fragment expected exactly one function s{slide}(s), got {functions}"
            )
        lowered = fragment.lower()
        if "require(" in lowered or "require (" in lowered:
            issues.append(
                f"{label} fragment must use the shared kit without require(...)"
            )
        if (
            "target ===" in lowered
            or "target===" in lowered
            or "pptx" in lowered
            and "html" in lowered
            and "if" in lowered
        ):
            issues.append(
                f"{label} fragment contains forbidden backend-specific branching"
            )
        source_name = f"slide{slide}.png".lower()
        if source_name in lowered:
            issues.append(
                f"{label} fragment references the full source PNG {source_name}"
            )

    score = _read_worker_json(work_dir / "reconstruction_score.json", issues, label)
    if score is not None:
        if score.get("slide") != slide:
            issues.append(f"{label} reconstruction_score.slide must be {slide}")
        if score.get("quality") != "reconstruction" or score.get("status") != "pass":
            issues.append(
                f"{label} reconstruction_score must record reconstruction pass"
            )

    qa_result = _read_worker_json(work_dir / "qa_result.json", issues, label)
    if qa_result is not None:
        if qa_result.get("slide") != slide or qa_result.get("status") != "pass":
            issues.append(f"{label} qa_result.json must record slide {slide} pass")
        for key in ("visualFidelity", "nativeEditability", "cropPolicy"):
            if qa_result.get(key) != "pass":
                issues.append(f"{label} qa_result.{key} must be pass")
        for key in ("blockingIssues", "noticeableIssues", "minorIssues"):
            if not isinstance(qa_result.get(key), list):
                issues.append(f"{label} qa_result.{key} must be an array")
        if qa_result.get("blockingIssues"):
            issues.append(f"{label} qa_result.blockingIssues must be empty")
        evidence_ref = str(
            qa_result.get("qaEvidence", qa_result.get("evidence", ""))
        ).replace("\\", "/")
        if (
            not evidence_ref.endswith(f"work/slide{slide:02d}/qa_evidence.json")
            and evidence_ref != "qa_evidence.json"
        ):
            issues.append(f"{label} qa_result.json must reference qa_evidence.json")

    evidence = _read_worker_json(work_dir / "qa_evidence.json", issues, label)
    if evidence is not None:
        if evidence.get("slide") != slide:
            issues.append(f"{label} qa_evidence.slide must be {slide}")
        if evidence.get("sourceHash") != job["source_png"]["sha256"]:
            issues.append(f"{label} qa_evidence sourceHash must match the selected PNG")
        visual = evidence.get("visualComparison")
        if not isinstance(visual, dict) or visual.get("status") != "pass":
            issues.append(f"{label} qa_evidence visualComparison must record pass")
        elif not str(visual.get("method", "")).strip():
            issues.append(f"{label} qa_evidence visualComparison.method is required")
        if not str(evidence.get("checkedAt", "")).strip():
            issues.append(f"{label} qa_evidence.checkedAt is required")
        if not str(evidence.get("checkedBy", "")).strip():
            issues.append(f"{label} qa_evidence.checkedBy is required")
        expected_source = root / job["source_png"]["path"]
        _validate_evidence_file(
            root,
            work_dir,
            evidence,
            path_key="sourceImage",
            hash_key="sourceHash",
            label=label,
            issues=issues,
            expected_path=expected_source,
        )
        _validate_evidence_file(
            root,
            work_dir,
            evidence,
            path_key="pptxRaster",
            hash_key="pptxRasterHash",
            label=label,
            issues=issues,
        )
        _validate_evidence_file(
            root,
            work_dir,
            evidence,
            path_key="htmlScreenshot",
            hash_key="htmlScreenshotHash",
            label=label,
            issues=issues,
        )

    for markdown_name in (
        "reconstruction_notes.md",
        "editability_inventory.md",
        "qa_report.md",
    ):
        try:
            value = (work_dir / markdown_name).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            issues.append(f"{label} {markdown_name} is not valid UTF-8: {exc}")
            continue
        if len(value.strip()) < 20:
            issues.append(f"{label} {markdown_name} is too short to be evidence")
        if re.search(
            r"mostly\s+baked|preservation\s+only|qa\s+pending|not\s+run", value, re.I
        ):
            issues.append(f"{label} {markdown_name} contains non-production wording")

    receipt = _read_worker_json(work_dir / "worker_receipt.json", issues, label)
    if receipt is None:
        return
    binding = job["receipt_binding"]
    expected_fields = {
        "slide": slide,
        "agent": "slide_reconstruct_worker",
        "status": "completed",
        "sharedFilesEdited": False,
        "jobId": job["job_id"],
        "jobContentHash": job["content_hash"],
        "sourcePngSha256": binding["source_png_sha256"],
        "imageRequestSha256": binding["image_request_sha256"],
        "semanticSidecarSha256": binding["semantic_sidecar_sha256"],
        "vectorPreflightSha256": binding["vector_preflight_sha256"],
        "vectorSlideContentHash": binding["vector_slide_content_hash"],
    }
    for key, value in expected_fields.items():
        if receipt.get(key) != value:
            issues.append(f"{label} worker_receipt.{key} must be {value!r}")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, list):
        issues.append(f"{label} worker_receipt.artifacts must be an array")
        artifacts = []
    expected_artifacts = [name for name in required if name != "worker_receipt.json"]
    if sorted(artifacts) != sorted(expected_artifacts):
        issues.append(f"{label} worker_receipt.artifacts must list every worker output")
    artifact_hashes = receipt.get("artifactHashes")
    if not isinstance(artifact_hashes, dict):
        issues.append(f"{label} worker_receipt.artifactHashes must be an object")
    else:
        for name in expected_artifacts:
            path = work_dir / name
            if path.is_file() and artifact_hashes.get(name) != _sha256_file(path):
                issues.append(
                    f"{label} worker_receipt artifact hash mismatch for {name}"
                )


def _validate_vector_usage(
    payload: dict[str, Any],
    job: dict[str, Any],
    label: str,
    issues: list[str],
) -> None:
    preflight = job["vector_preflight"]
    binding = job["receipt_binding"]
    expected_fields = {
        "slide": job["slide_number"],
        "policyId": preflight["policy_id"],
        "vectorPreflightSha256": binding["vector_preflight_sha256"],
        "vectorSlideContentHash": binding["vector_slide_content_hash"],
        "measurementInventorySha256": preflight["measurement_inventory"]["sha256"],
        "measuredCoordinatesAuthoritative": True,
    }
    for key, value in expected_fields.items():
        if payload.get(key) != value:
            issues.append(f"{label} vector_usage.{key} must be {value!r}")

    candidates = {
        region["region_id"]: region
        for region in preflight["regions"]
        if region.get("disposition") == "bounded_svg_asset"
    }
    used = payload.get("usedRegions")
    deferred = payload.get("deferredRegions")
    icon_uses = payload.get("parametricIconUses")
    if not isinstance(used, list):
        issues.append(f"{label} vector_usage.usedRegions must be an array")
        used = []
    if not isinstance(deferred, list):
        issues.append(f"{label} vector_usage.deferredRegions must be an array")
        deferred = []
    if not isinstance(icon_uses, list):
        issues.append(f"{label} vector_usage.parametricIconUses must be an array")
        icon_uses = []
    accounted: list[str] = []
    for row in used:
        if not isinstance(row, dict) or not str(row.get("regionId", "")).strip():
            issues.append(f"{label} vector_usage used region must name regionId")
            continue
        region_id = str(row["regionId"])
        accounted.append(region_id)
        candidate = candidates.get(region_id)
        if candidate is None:
            issues.append(f"{label} vector_usage uses non-approved SVG region {region_id}")
            continue
        if row.get("assetSha256") != candidate["vector_svg"]["sha256"]:
            issues.append(f"{label} vector_usage asset hash mismatch for {region_id}")
    for row in deferred:
        if not isinstance(row, dict) or not str(row.get("regionId", "")).strip():
            issues.append(f"{label} vector_usage deferred region must name regionId")
            continue
        region_id = str(row["regionId"])
        accounted.append(region_id)
        if region_id not in candidates:
            issues.append(f"{label} vector_usage defers non-approved SVG region {region_id}")
        if len(str(row.get("reason", "")).strip()) < 8:
            issues.append(f"{label} vector_usage deferred region {region_id} needs a reason")
    if sorted(accounted) != sorted(candidates):
        issues.append(
            f"{label} vector_usage must use or defer every approved bounded SVG region"
        )
    if len(accounted) != len(set(accounted)):
        issues.append(f"{label} vector_usage contains duplicate region decisions")
    measured_regions = {
        region["region_id"]: region for region in preflight["regions"]
    }
    allowed_icons = set(preflight["available_parametric_icon_names"])
    icon_region_ids: list[str] = []
    for row in icon_uses:
        if not isinstance(row, dict):
            issues.append(f"{label} vector_usage parametric icon use must be an object")
            continue
        name = str(row.get("name", ""))
        region_id = str(row.get("regionId", ""))
        region = measured_regions.get(region_id)
        icon_region_ids.append(region_id)
        if name not in allowed_icons:
            issues.append(f"{label} vector_usage uses unknown parametric icon {name}")
        if region is None:
            issues.append(f"{label} vector_usage icon {name} has unknown region {region_id}")
            continue
        if region.get("semantic_text_overlap_ids"):
            issues.append(f"{label} vector_usage icon {name} overlaps semantic text")
        if region.get("area_ratio", 1) > 0.35 or region.get("kind_hint") == "photo":
            issues.append(f"{label} vector_usage icon {name} is not a bounded icon region")
        color = str(row.get("color", ""))
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            issues.append(f"{label} vector_usage icon {name} needs a #RRGGBB color")
    if len(icon_region_ids) != len(set(icon_region_ids)):
        issues.append(f"{label} vector_usage duplicates a parametric icon region")


def _validate_integrated_outputs(
    root: Path,
    jobs: list[dict[str, Any]],
    issues: list[str],
) -> None:
    project = root / PROJECT_DIRECTORY
    slides_path = project / "lib" / "slides.js"
    report_path = project / "work" / "integration_report.md"
    crop_plan_path = project / "work" / "crop_plan.json"
    try:
        slides_source = slides_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        issues.append(f"integrator output lib/slides.js cannot be read: {exc}")
        slides_source = ""
    if slides_source:
        expected_functions = [f"s{row['lineage']['slide_number']}" for row in jobs]
        actual_functions = re.findall(
            r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(\s*s\s*\)",
            slides_source,
        )
        for function_name in expected_functions:
            if actual_functions.count(function_name) != 1:
                issues.append(
                    f"integrator output must contain exactly one function {function_name}(s)"
                )
        unexpected = sorted(set(actual_functions) - set(expected_functions))
        if unexpected:
            issues.append(
                f"integrator output contains unexpected slide functions {unexpected}"
            )
        if "module.exports" not in slides_source:
            issues.append(
                "integrator output lib/slides.js must export the slide functions"
            )
        for row in jobs:
            source_name = f"slide{row['lineage']['slide_number']}.png".lower()
            if source_name in slides_source.lower():
                issues.append(
                    f"integrator output references forbidden full source PNG {source_name}"
                )

    try:
        report = report_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        issues.append(f"integrator output integration_report.md cannot be read: {exc}")
        report = ""
    if report:
        if "# Sub-Agent Integration Report" not in report:
            issues.append(
                "integration report must be produced by the official integrator"
            )
        for row in jobs:
            slide = row["lineage"]["slide_number"]
            if f"## s{slide}" not in report:
                issues.append(f"integration report is missing slide s{slide}")
        if re.search(r":\s*missing\b", report, re.I):
            issues.append("integration report contains missing worker artifacts")

    try:
        crop_plan = read_json(crop_plan_path)
    except (OSError, ValueError, TypeError) as exc:
        issues.append(f"integrated crop_plan.json cannot be read: {exc}")
    else:
        if not isinstance(crop_plan, dict):
            issues.append("integrated crop_plan.json must be an object")


def _validate_evidence_file(
    root: Path,
    work_dir: Path,
    evidence: dict[str, Any],
    *,
    path_key: str,
    hash_key: str,
    label: str,
    issues: list[str],
    expected_path: Path | None = None,
) -> None:
    raw = evidence.get(path_key)
    if not isinstance(raw, str) or not raw.strip():
        issues.append(f"{label} qa_evidence.{path_key} is required")
        return
    project = root / PROJECT_DIRECTORY
    candidate = Path(raw)
    if candidate.is_absolute():
        path = candidate.resolve()
    else:
        project_candidate = (project / candidate).resolve()
        path = (
            project_candidate
            if project_candidate.is_file()
            else (work_dir / candidate).resolve()
        )
    if path != project and not path.is_relative_to(project):
        issues.append(f"{label} qa_evidence.{path_key} escapes the project")
        return
    if expected_path is not None and path != expected_path.resolve():
        issues.append(f"{label} qa_evidence.{path_key} must match the selected PNG")
    if not path.is_file():
        issues.append(f"{label} qa_evidence.{path_key} is missing: {path}")
        return
    expected_hash = evidence.get(hash_key)
    if not isinstance(expected_hash, str) or expected_hash != _sha256_file(path):
        issues.append(f"{label} qa_evidence {hash_key} mismatch")


def _accepted_calls(
    batch: dict[str, Any], slide_count: int
) -> dict[int, dict[str, Any]]:
    if batch.get("schema_name") != "image_generation_batch_manifest":
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            "image generation batch manifest schema_name is invalid",
        )
    if batch.get("platform_tool_id") != "image_gen.imagegen":
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            "image generation must use image_gen.imagegen",
        )
    if (
        batch.get("slide_count") != slide_count
        or batch.get("accepted_count") != slide_count
    ):
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            "image generation batch must accept exactly one image per slide",
        )
    calls: dict[int, dict[str, Any]] = {}
    for wave in batch.get("waves", []):
        if not isinstance(wave, dict) or wave.get("concurrent_dispatch") is not True:
            raise _error(
                "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
                "every image generation wave must use concurrent_dispatch",
            )
        for call in wave.get("calls", []):
            if not isinstance(call, dict) or call.get("status") != "ACCEPTED":
                continue
            slide = call.get("slide_number")
            if not isinstance(slide, int) or slide in calls:
                raise _error(
                    "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
                    "image generation batch contains an invalid or duplicate slide call",
                )
            calls[slide] = call
    if sorted(calls) != list(range(1, slide_count + 1)):
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            f"accepted image calls must cover slides 1..{slide_count}",
        )
    return calls


def _validate_crops(
    payload: dict[str, Any],
    slide: int,
    source: dict[str, Any],
    issues: list[str],
) -> None:
    raw = payload.get("crops", payload)
    if isinstance(raw, dict):
        crops = [
            dict(value, name=value.get("name", name))
            for name, value in raw.items()
            if isinstance(value, dict)
        ]
    elif isinstance(raw, list):
        crops = raw
    else:
        issues.append(f"slide {slide} worker crop_plan.json must contain crops")
        return
    for index, crop in enumerate(crops):
        if not isinstance(crop, dict):
            issues.append(f"slide {slide} worker crop {index} must be an object")
            continue
        name = str(crop.get("name", ""))
        if not name.startswith(f"s{slide}"):
            issues.append(f"slide {slide} worker crop names must be prefixed s{slide}")
        if int(_number(crop.get("slide"), default=-1)) != slide:
            issues.append(f"slide {slide} worker crop {name or index} has wrong slide")
        values = {
            key: _number(crop.get(key), default=-1) for key in ("x", "y", "w", "h")
        }
        if (
            any(value < 0 for value in values.values())
            or values["w"] <= 0
            or values["h"] <= 0
        ):
            issues.append(
                f"slide {slide} worker crop {name or index} has invalid geometry"
            )
            continue
        area = values["w"] * values["h"]
        canvas_area = source["width"] * source["height"]
        if area / canvas_area > 0.45:
            issues.append(
                f"slide {slide} worker crop {name or index} exceeds 45% of slide area"
            )
        content_type = str(
            crop.get("content_type", crop.get("contentType", ""))
        ).strip()
        reason = str(crop.get("reconstruction_reason", "")).strip()
        replacement = str(crop.get("editable_replacement", "")).strip()
        if not content_type or not reason or not replacement:
            issues.append(
                f"slide {slide} worker crop {name or index} needs content_type, "
                "reconstruction_reason, and editable_replacement"
            )


def _read_worker_json(
    path: Path, issues: list[str], label: str
) -> dict[str, Any] | None:
    try:
        payload = read_json(path)
    except (OSError, ValueError, TypeError) as exc:
        issues.append(f"{label} {path.name} is invalid JSON: {exc}")
        return None
    if not isinstance(payload, dict):
        issues.append(f"{label} {path.name} must be an object")
        return None
    return payload


def _required_artifact_path(root: Path, artifact: Any, label: str) -> Path:
    if not isinstance(artifact, dict):
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID", f"{label} artifact is missing"
        )
    path = _resolve_inside(root, artifact.get("path"), label)
    if path is None or not path.is_file():
        raise _error("DC_RECONSTRUCTION_JOB_INPUT_INVALID", f"{label} is missing")
    actual = _sha256_file(path)
    if artifact.get("sha256") != actual:
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID", f"{label} sha256 mismatch", path
        )
    return path


def _resolve_inside(root: Path, value: Any, label: str) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    path = (
        candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    )
    if path != root and not path.is_relative_to(root):
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            f"{label} must stay inside the workflow runtime",
            path,
        )
    if path.is_symlink():
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            f"{label} must not be a symlink",
            path,
        )
    return path


def _png_dimensions(path: Path) -> tuple[int, int]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            f"source PNG is missing: {path}",
            path,
        ) from exc
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            f"source image is not a structurally valid PNG: {path}",
            path,
        )
    width, height = struct.unpack(">II", data[16:24])
    if width <= 0 or height <= 0 or abs((width / height) - (16 / 9)) > 0.02:
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID",
            f"source PNG must be 16:9, got {width}x{height}",
            path,
        )
    return width, height


def _artifact(root: Path, path: Path) -> dict[str, str]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise _error(
            "DC_RECONSTRUCTION_JOB_INPUT_INVALID", f"artifact is missing: {resolved}"
        )
    return {
        "path": resolved.relative_to(root).as_posix(),
        "sha256": _sha256_file(resolved),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _number(value: Any, *, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _error(code: str, message: str, path: Path | None = None) -> DeckCompilerError:
    return DeckCompilerError(
        code,
        "general_generate_workflow",
        message,
        path.as_posix() if path else None,
        remediation_hint=(
            "Re-run deterministic job preparation after ImageGen selection, then execute "
            "one isolated slide-image-dual-render reconstruction context per job."
        ),
    )


__all__ = [
    "AUTHORING_OUTPUT_NAMES",
    "JOB_MANIFEST_NAME",
    "MAX_PARALLEL_WORKERS",
    "POST_RENDER_OUTPUT_NAMES",
    "REQUIRED_OUTPUT_NAMES",
    "ReconstructionJobPreparationResult",
    "ReconstructionSlideJobPreparationResult",
    "prepare_reconstruction_job",
    "prepare_reconstruction_jobs",
    "validate_reconstruction_job_bundle",
]
