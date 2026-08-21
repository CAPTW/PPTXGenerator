"""Architect-first Codex entrypoint for prompt/PDF-to-editable-PPTX workflows."""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..errors import DeckCompilerError
from ..identity import content_sha256, stable_id
from ..manifest_io import read_json, write_json
from ..provenance import current_source_commit
from ..schemas import REPO_ROOT, validator_for
from .codex_run import validate_codex_run_manifest
from .execution_profiles import DEFAULT_EXECUTION_PROFILE
from .skillset_plan import (
    PLAN_NAME,
    build_skillset_execution_plan,
    inspect_skillset,
    scaffold_runtime_project,
    validate_skillset_execution_plan,
)


MANIFEST_NAME = "generate_workflow_manifest.json"
DISPATCH_NAME = "codex_dispatch.json"
RUNBOOK_NAME = "CODEX_WORKFLOW.md"
WORKFLOW_SCHEMA = "general_generate_workflow_manifest"
MAX_GENERAL_PDFS = 50


@dataclass(frozen=True, slots=True)
class GenerateWorkflowResult:
    workflow_id: str
    runtime_root: Path
    manifest_path: Path
    status: str
    exit_code: int
    required_action: dict[str, Any] | None


def start_generate_workflow(
    *,
    output_dir: Path,
    prompt: str | None,
    prompt_file: Path | None,
    pdf_paths: Iterable[Path],
    audience: str,
    purpose: str,
    language: str,
    tone: Iterable[str],
    workflow: str,
    skill_root: Path | None = None,
    execution_profile: str = DEFAULT_EXECUTION_PROFILE,
) -> GenerateWorkflowResult:
    """Collect immutable inputs and stop at the mandatory Architect-first gate."""

    skillset = inspect_skillset(skill_root)
    root = _prepare_runtime_root(output_dir)
    manifest: dict[str, Any] | None = None
    try:
        prompt_text = _resolve_prompt(prompt, prompt_file)
        pdf_sources = _resolve_pdfs(pdf_paths)
        tone_values = tuple(value.strip() for value in tone if value.strip())
        presentation = {
            "audience": audience.strip(),
            "purpose": purpose.strip(),
            "language": language.strip(),
            "tone": list(tone_values),
            "workflow_hint": workflow.strip() or "auto",
        }
        if not tone_values:
            raise _workflow_error(
                "DC_GENERATE_INPUT_INVALID",
                "At least one non-empty tone is required.",
            )
        if not all(
            (
                presentation["audience"],
                presentation["purpose"],
                presentation["language"],
            )
        ):
            raise _workflow_error(
                "DC_GENERATE_INPUT_INVALID",
                "Audience, purpose, and language must be non-empty.",
            )

        inputs_dir = root / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=False)
        prompt_path = inputs_dir / "prompt.txt"
        _atomic_write_text(prompt_path, prompt_text.strip() + "\n")
        copied_pdfs = _copy_pdf_inputs(pdf_sources, inputs_dir)
        mode = "prompt_with_pdfs" if copied_pdfs else "prompt_only"
        workflow_id = stable_id(
            "generate",
            prompt_text,
            [_sha256_file(path) for path in copied_pdfs],
            presentation,
        )
        input_contract = {
            "mode": mode,
            "prompt": _artifact_reference(root, prompt_path, "user_prompt"),
            "pdfs": [
                _artifact_reference(root, path, "user_pdf") for path in copied_pdfs
            ],
            "presentation": presentation,
        }
        scaffold_runtime_project(root)
        execution_plan = build_skillset_execution_plan(
            workflow_id=workflow_id,
            runtime_root=root,
            inspection=skillset,
            execution_profile_name=execution_profile,
        )
        execution_plan_path = write_json(root / PLAN_NAME, execution_plan)
        dispatch = _dispatch_payload(
            workflow_id,
            input_contract,
            skillset=skillset,
            execution_profile=execution_plan["execution_profile"],
        )
        dispatch_path = write_json(root / DISPATCH_NAME, dispatch)
        runbook_path = root / RUNBOOK_NAME
        _atomic_write_text(runbook_path, _dispatch_runbook(workflow_id))

        created_at = _now()
        manifest = _initial_manifest(
            root,
            workflow_id,
            created_at,
            input_contract,
            dispatch_path,
            runbook_path,
            execution_plan_path,
        )
        _sync_artifacts(manifest)
        _write_workflow_manifest(root, manifest)
        return _result(root, manifest, exit_code=2)
    except Exception as exc:
        if manifest is not None:
            _block_manifest(root, manifest, exc)
        raise


def resume_generate_workflow(
    *,
    resume: Path,
    codex_run_manifest: Path | None = None,
) -> GenerateWorkflowResult:
    """Register a sealed live Codex run and accept only quality-gated completion."""

    root, manifest = _load_workflow(resume)
    if manifest["status"] == "COMPLETED":
        return _result(root, manifest, exit_code=0)
    if codex_run_manifest is None:
        return _result(
            root,
            manifest,
            exit_code=1 if manifest["status"] == "NEEDS_REPAIR" else 2,
        )

    try:
        run_path = codex_run_manifest.resolve()
        report = validate_codex_run_manifest(
            run_path,
            expected_workflow_id=manifest["workflow_id"],
        )
        if not report["contract_valid"]:
            raise _workflow_error(
                "DC_CODEX_RUN_INVALID",
                "; ".join(report["issues"][:8]),
                artifact_path=run_path,
                remediation_hint=(
                    "Run the live pptx-generator-workflow, preserve real Skill execution "
                    "artifacts, and reseal codex_run.json."
                ),
            )

        payload = read_json(run_path)
        _bind_codex_run_artifacts(root, manifest, run_path, payload)
        if report["completion_ready"]:
            for stage in manifest["stages"]:
                stage["status"] = "COMPLETED"
                stage["required_action"] = None
            manifest["status"] = "COMPLETED"
            _record(manifest, "codex_live_workflow_accepted", "COMPLETED")
            _sync_artifacts(manifest)
            _write_workflow_manifest(root, manifest)
            return _result(root, manifest, exit_code=0)

        reconstruction = _stage(manifest, "reconstruction")
        qa = _stage(manifest, "visual_qa")
        delivery = _stage(manifest, "delivery")
        reconstruction["status"] = "NEEDS_REPAIR"
        qa["status"] = "NEEDS_REPAIR"
        delivery["status"] = "PENDING"
        action = {
            "code": "CONTINUE_PNGTOPPTX_REPAIR_WAVES",
            "message": (
                "Continue slide-editable-deck-orchestrator repair waves and visual QA "
                "until fail_count and blocking_count are zero, then reseal the run."
            ),
            "completion_issues": report["completion_issues"],
        }
        reconstruction["required_action"] = action
        qa["required_action"] = None
        delivery["required_action"] = None
        manifest["status"] = "NEEDS_REPAIR"
        _record(manifest, "codex_live_workflow_needs_repair", "NEEDS_REPAIR")
        _sync_artifacts(manifest)
        _write_workflow_manifest(root, manifest)
        return _result(root, manifest, exit_code=1)
    except Exception as exc:
        _block_manifest(root, manifest, exc)
        raise


def validate_generate_workflow(path: Path) -> dict[str, Any]:
    manifest_path = path / MANIFEST_NAME if path.is_dir() else path
    payload = read_json(manifest_path)
    issues = _manifest_issues(payload)
    if not issues:
        root = manifest_path.resolve().parent
        issues.extend(_input_artifact_issues(root, payload))
        issues.extend(_manifest_artifact_issues(root, payload))
        issues.extend(_skillset_plan_issues(root, payload))
        issues.extend(_sealed_run_issues(root, payload))
    return {
        "valid": not issues,
        "status": payload.get("status"),
        "workflow_id": payload.get("workflow_id"),
        "required_first_skill": payload.get("dispatch", {}).get("required_first_skill"),
        "issues": issues,
    }


def _initial_manifest(
    root: Path,
    workflow_id: str,
    created_at: str,
    input_contract: dict[str, Any],
    dispatch_path: Path,
    runbook_path: Path,
    execution_plan_path: Path,
) -> dict[str, Any]:
    action = {
        "code": "INVOKE_PPTX_WORKFLOW_ARCHITECT",
        "message": (
            "In Codex, read and invoke pptx-workflow-architect before any planning, "
            "Image Generation, or PNGtoPPTX execution. Complete and approve Gates 1 and 2, "
            "then follow the repo pptx-generator-workflow Skill."
        ),
        "required_first_skill": "pptx-workflow-architect",
        "required_first_skill_path": (
            ".agents/skills/pptx-workflow-architect/SKILL.md"
        ),
        "production_skill_path": (".agents/skills/pptx-generator-workflow/SKILL.md"),
    }
    return {
        "schema_name": WORKFLOW_SCHEMA,
        "schema_version": "2.0.0",
        "workflow_id": workflow_id,
        "entrypoint": "deckcompiler generate",
        "source_commit": current_source_commit(),
        "runtime_root": root.as_posix(),
        "created_at": created_at,
        "updated_at": created_at,
        "status": "AWAITING_WORKFLOW_ARCHITECT",
        "input_contract": input_contract,
        "dispatch": {
            "required_first_skill": "pptx-workflow-architect",
            "required_first_skill_path": (
                ".agents/skills/pptx-workflow-architect/SKILL.md"
            ),
            "production_skill": "pptx-generator-workflow",
            "image_skill": "imagegen",
            "image_tool": "image_gen.imagegen",
            "reconstruction_skill": "slide-editable-deck-orchestrator",
            "renderer_skill": "slide-image-dual-render",
            "visual_qa_skill": "slide-visual-polish-qa",
            "skillset_execution_plan": PLAN_NAME,
            "default_quality_level": "polish",
            "approval_policy": ("architect_gate1_and_gate2_explicit_user_approval"),
        },
        "stages": [
            {
                "stage": "architect",
                "status": "AWAITING_EXTERNAL",
                "artifacts": [
                    _artifact_reference(root, dispatch_path, "codex_dispatch"),
                    _artifact_reference(root, runbook_path, "codex_workflow_runbook"),
                    _artifact_reference(
                        root,
                        execution_plan_path,
                        "skillset_execution_plan",
                    ),
                ],
                "required_action": action,
                "details": {
                    "gate1": "PENDING",
                    "gate2": "PENDING",
                    "fixed_slide_count_forbidden": True,
                },
            },
            _pending_stage("image_generation"),
            _pending_stage("reconstruction"),
            _pending_stage("visual_qa"),
            _pending_stage("delivery"),
        ],
        "artifacts": [],
        "history": [
            {
                "timestamp": created_at,
                "event": "workflow_created_architect_first",
                "status": "AWAITING_WORKFLOW_ARCHITECT",
            }
        ],
        "errors": [],
        "manifest_hash": "0" * 64,
    }


def _pending_stage(name: str) -> dict[str, Any]:
    return {
        "stage": name,
        "status": "PENDING",
        "artifacts": [],
        "required_action": None,
        "details": {},
    }


def _dispatch_payload(
    workflow_id: str,
    input_contract: dict[str, Any],
    *,
    skillset: dict[str, Any],
    execution_profile: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "schema_name": "pptx_generator_codex_dispatch",
        "schema_version": "1.3.0",
        "workflow_id": workflow_id,
        "input_contract": input_contract,
        "skillset_execution_plan": PLAN_NAME,
        "skillset_preflight": {
            "status": skillset["status"],
            "repository_skill_root": skillset["repository_skill_root"],
            "external_skill_root": skillset["skill_root"],
        },
        "execution_profile": execution_profile,
        "skill_sequence": [
            {
                **row,
                **(
                    {
                        "required_outputs": [
                            "gate1_workflow_design",
                            "gate2_blueprint",
                            "gate2_design_system",
                            "explicit_user_approval",
                        ]
                    }
                    if row["skill_name"] == "pptx-workflow-architect"
                    else {
                        "platform_tool_id": "image_gen.imagegen",
                        "request_preparation": (
                            "deckcompiler prepare-image-requests --runtime <runtime>"
                        ),
                        "request_manifest": (
                            "image_requests/image_request_manifest.json"
                        ),
                        "streaming_preparation": (
                            "deckcompiler prepare-streaming-execution "
                            "--runtime <runtime>"
                        ),
                        "accept_completed_image": (
                            "deckcompiler accept-streaming-image --runtime "
                            "<runtime> --slide <N> --tool-call-id <id> "
                            "--queued-at <time> --started-at <time> "
                            "--completed-at <time>"
                        ),
                        "required_coverage": (
                            "one inspected selected PNG per approved slide"
                        ),
                        "dispatch_mode": "concurrent_wave",
                        "acceptance_mode": "streaming_ready_queue",
                        "batch_size": 20,
                        "call_strategy": "one_independent_builtin_call_per_slide",
                        "reconstruction_starts_before_wave_complete": True,
                        "max_parallel_reconstruction_workers": 6,
                    }
                    if row["skill_name"] == "imagegen"
                    else {
                        "execution_contract": (
                            "follow skillset_execution_plan.json official entrypoints"
                        )
                    }
                ),
            }
            for row in skillset["skills"]
        ],
        "slide_count_policy": (
            "architect_approved_right_sized_count_1_to_400_no_fixed_six_slide_template"
        ),
        "finalization": {
            "seal_command": (
                "deckcompiler seal-codex-run --draft <draft> --output <codex_run.json>"
            ),
            "register_command": (
                "deckcompiler generate --resume <runtime> "
                "--codex-run-manifest <codex_run.json>"
            ),
        },
    }
    payload["dispatch_hash"] = content_sha256(payload)
    return payload


def _dispatch_runbook(workflow_id: str) -> str:
    return f"""# Codex PPTX Workflow

Workflow ID: `{workflow_id}`

1. Read `.agents/skills/pptx-workflow-architect/SKILL.md` first, including the
   reference files it requires for the active Gate.
2. Complete Architect Gate 1 and Gate 2 and obtain explicit user approval.
3. Read `.agents/skills/pptx-generator-workflow/SKILL.md` and the installed
   ImageGen plus four PNGtoPPTX companion Skills listed in
   `skillset_execution_plan.json`.
4. Persist the approved Architect JSON package, then run
   `deckcompiler prepare-image-requests --runtime <runtime>` exactly once. This
   deterministic, no-model-call adapter creates every Prompt and Semantic
   Sidecar from the approved Blueprint and Design System and writes their
   hash-bound lineage manifest. Do not hand-author or summarize the prompts a
   second time. The concise default direction is `Academic, Informative,
   Professional, Creative`; preserve the approved route without blanket layout
   bans, a hard element-count cap, or a mandatory three-second rule.
5. Run `deckcompiler prepare-streaming-execution --runtime <runtime>`, then
   dispatch up to 20 independent built-in `image_gen.imagegen` calls as one
   concurrent wave. This is still one platform call per slide, not a mock,
   repository CLI fallback, or one multi-image API call. For a 20-slide deck,
   submit all 20 initial calls together and keep the unfinished calls running.
   Retry only a failed slide, at most once; never restart the whole wave.
6. As each result completes, inspect it, save it as
   `pngtopptx-project/src/slideN.png`, run the native-canvas `PPTXlocal/raw`
   measurement and bounded PNG-to-SVG preflight for that slide, then immediately
   run `deckcompiler accept-streaming-image` with the real tool-call timestamps.
   Only security/fidelity-gated non-text flat regions may become SVG; semantic
   text, continuous-tone regions, and the complete slide must remain outside
   that vector path. A passing slide enters the reconstruction ready queue at
   once; it must not wait for the other nineteen images or the final batch.
7. Execute `setup`, record an explicit execute/skip decision for
   `slide-text-layer-inpaint`, and materialize the hard-locked renderer project.
8. Keep a ready queue of one-slide jobs while ImageGen is still in flight.
   Process each job in one fresh context containing only that source slide, its
   authoritative measured geometry/vector inventory, compact job, and Semantic
   Sidecar; run no more than six reconstruction
   workers concurrently. Each worker writes only its `work/slideXX/` authoring
   artifacts. Do not build an isolated PPTX/HTML for every slide. Record actual
   STARTED and AUTHORING_COMPLETED timestamps in `streaming_execution.json`.
9. After the last image is accepted, run `finalize-streaming-images` and
   `validate-streaming-execution --require-complete --require-overlap`. This
   seals the canonical batch/job manifests and proves that reconstruction began
   before the last ImageGen call completed. Validate authoring outputs, run the
   official `validate_agent_work.js`, and let the official
   `integrate_subagent_work.js` be the sole writer of `lib/slides.js` and the
   integrated crop plan. Do not hand-author a generic shared slide template.
10. Build one all-slide shared preview with the official renderer. Rasterize the
    preview PPTX and capture its HTML once, then reuse the source-mapped slide
    pages for every slide's Visual QA. Run `deckcompiler
    finalize-shared-render-qa` to close reconstruction receipts from that
    accepted evidence. This replaces
    twenty isolated dual renders; it does not remove any per-slide comparison,
    native-object, crop, exact-copy, or editability gate.
11. Apply the repository high-fidelity acceptance policy after the external
    visual QA gate. Only the known native-renderer diagnostics `palette_drift`
    and `pptx_html_edge_mismatch` may remain as `needs_polish`; spacing,
    hierarchy, typography, clipping, content, or detail loss enters repair.
12. After the shared preview receipts pass, run one final all-slide
    `slide_pipeline.js --quality reconstruction --require-qa
    --require-reconstruction --allow-large-batch` invocation and the final
    openability/full-deck gate. The normal no-repair path therefore uses two
    shared full-deck renders and zero isolated per-slide builds. If QA fails,
    repair only named blocking slides in waves of at most five, for no more than
    two iterations, then rerun the final full-deck gate/QA.
13. Never use a full-slide source PNG as the delivered slide surface. Keep
    `qa-polish`, hardlocks, openability, editability evidence, and zero
    fail/blocking acceptance unchanged.
14. Write `execution_timing.json`, including real ImageGen call intervals,
    observed parallelism, streaming overlap, and both shared render passes;
    seal `codex_run.json`, and register it with
    `deckcompiler generate --resume`. For 20 slides, record the 120-minute
    baseline, 30-minute target, actual duration, and whether the approximate
    4x target was met; quality gates always take precedence over the time target.

`skillset_execution_plan.json` is hash-bound and contains the exact installed
Skill paths, official script hashes, environment, command templates, artifact
contract, crop policy, and stop conditions. Do not replace it with a repo-local
renderer or an improvised command path.

This runtime is incomplete until the sealed run is accepted. Prompt preparation,
mocked tools, an invocation plan, or an unreviewed PPTX is not completion.
"""


def _bind_codex_run_artifacts(
    root: Path,
    manifest: dict[str, Any],
    run_path: Path,
    payload: dict[str, Any],
) -> None:
    base = run_path.parent
    architect = _stage(manifest, "architect")
    image = _stage(manifest, "image_generation")
    reconstruction = _stage(manifest, "reconstruction")
    qa = _stage(manifest, "visual_qa")
    delivery = _stage(manifest, "delivery")

    architect["status"] = "COMPLETED"
    architect["required_action"] = None
    architect["details"] = {
        "gate1": payload["architect"]["gate1"]["status"],
        "gate2": payload["architect"]["gate2"]["status"],
        "slide_count": payload["architect"]["slide_count"],
        "first_skill_invoked": payload["architect"]["first_skill_invoked"],
    }
    control_plane_artifacts = [
        artifact
        for artifact in architect["artifacts"]
        if artifact["kind"]
        in {
            "codex_dispatch",
            "codex_workflow_runbook",
            "skillset_execution_plan",
        }
    ]
    architect["artifacts"] = control_plane_artifacts + [
        _run_artifact_reference(
            root, base, payload["architect"][key], f"architect_{key}"
        )
        for key in (
            "workflow_design",
            "blueprint",
            "design_system",
            "approval_record",
        )
    ]

    image["status"] = "COMPLETED"
    image["required_action"] = None
    image["details"] = {
        "platform_tool_id": payload["image_generation"]["platform_tool_id"],
        "requested_slide_count": payload["image_generation"]["requested_slide_count"],
        "completed_slide_count": payload["image_generation"]["completed_slide_count"],
        "dispatch_profile": payload["image_generation"]["dispatch_profile"],
    }
    image["artifacts"] = [
        _run_artifact_reference(
            root,
            base,
            payload["image_generation"]["request_manifest"],
            "image_request_manifest",
        ),
        _run_artifact_reference(
            root,
            base,
            payload["image_generation"]["batch_manifest"],
            "image_generation_batch_manifest",
        ),
        *[
            _run_artifact_reference(
                root,
                base,
                row["source_png"],
                f"imagegen_slide_{row['slide_number']:03d}",
            )
            for row in payload["image_generation"]["slides"]
        ],
    ]

    reconstruction["status"] = "COMPLETED"
    reconstruction["required_action"] = None
    reconstruction["details"] = {
        "skill_name": payload["reconstruction"]["skill_name"],
        "renderer_skill": payload["reconstruction"]["renderer_skill"],
        "companion_skills": payload["reconstruction"]["companion_skills"],
        "text_layer_preprocessing": payload["reconstruction"][
            "text_layer_preprocessing"
        ],
        "quality_level": payload["reconstruction"]["quality_level"],
        "route_hardlock": payload["reconstruction"]["route_hardlock"],
        "reconstruction_hardlock": payload["reconstruction"]["reconstruction_hardlock"],
        "pptx_openability": payload["reconstruction"]["pptx_openability"],
    }
    reconstruction["artifacts"] = [
        _run_artifact_reference(
            root,
            base,
            payload["reconstruction"]["execution_plan"],
            "skillset_execution_plan",
        ),
        _run_artifact_reference(
            root,
            base,
            payload["reconstruction"]["orchestration_state"],
            "pngtopptx_orchestration_state",
        ),
        _run_artifact_reference(
            root,
            base,
            payload["reconstruction"]["render_trace"],
            "pngtopptx_render_trace",
        ),
        _run_artifact_reference(
            root,
            base,
            payload["reconstruction"]["crop_plan"],
            "pngtopptx_crop_plan",
        ),
        _run_artifact_reference(
            root,
            base,
            payload["reconstruction"]["crop_manifest"],
            "pngtopptx_crop_manifest",
        ),
        _run_artifact_reference(
            root,
            base,
            payload["reconstruction"]["crop_coverage_summary"],
            "pngtopptx_crop_coverage_summary",
        ),
        _run_artifact_reference(
            root,
            base,
            payload["reconstruction"]["qa_evidence_summary"],
            "pngtopptx_qa_evidence_summary",
        ),
        _run_artifact_reference(
            root,
            base,
            payload["reconstruction"]["output_pptx"],
            "editable_pptx",
        ),
        _run_artifact_reference(
            root,
            base,
            payload["reconstruction"]["native_object_manifest"],
            "native_object_manifest",
        ),
        _run_artifact_reference(
            root,
            base,
            payload["reconstruction"]["openability_report"],
            "pptx_openability_report",
        ),
    ]
    if payload["reconstruction"]["output_html"] is not None:
        reconstruction["artifacts"].append(
            _run_artifact_reference(
                root,
                base,
                payload["reconstruction"]["output_html"],
                "editable_html",
            )
        )

    qa["status"] = (
        "COMPLETED" if payload["visual_qa"]["status"] == "PASS" else "NEEDS_REPAIR"
    )
    qa["required_action"] = None
    qa["details"] = {
        "skill_name": payload["visual_qa"]["skill_name"],
        "status": payload["visual_qa"]["status"],
        "fail_count": payload["visual_qa"]["fail_count"],
        "blocking_count": payload["visual_qa"]["blocking_count"],
        "needs_polish_count": payload["visual_qa"]["needs_polish_count"],
        "repair_iterations": payload["visual_qa"]["repair_iterations"],
    }
    qa["artifacts"] = [
        _run_artifact_reference(
            root, base, payload["visual_qa"]["summary"], "visual_qa_summary"
        ),
        _run_artifact_reference(
            root,
            base,
            payload["visual_qa"]["summary_markdown"],
            "visual_qa_summary_markdown",
        ),
        _run_artifact_reference(
            root, base, payload["visual_qa"]["contact_sheet"], "contact_sheet"
        ),
    ]

    delivery["status"] = "COMPLETED" if payload["status"] == "COMPLETED" else "PENDING"
    delivery["required_action"] = None
    delivery["details"] = {
        "format": payload["delivery"]["format"],
        "performance_profile": payload["performance"]["profile_name"],
        "target_minutes_20_slides": payload["performance"]["target_minutes_20_slides"],
    }
    delivery["artifacts"] = [
        _artifact_reference(root, run_path, "sealed_codex_run_manifest"),
        _run_artifact_reference(
            root, base, payload["delivery"]["pptx"], "delivered_editable_pptx"
        ),
        _run_artifact_reference(
            root,
            base,
            payload["delivery"]["editability_inventory"],
            "editability_inventory",
        ),
        _run_artifact_reference(
            root,
            base,
            payload["performance"]["timing_report"],
            "execution_timing",
        ),
    ]
    if payload["delivery"]["html"] is not None:
        delivery["artifacts"].append(
            _run_artifact_reference(
                root, base, payload["delivery"]["html"], "delivered_editable_html"
            )
        )


def _run_artifact_reference(
    root: Path,
    manifest_base: Path,
    value: dict[str, Any],
    kind: str,
) -> dict[str, Any]:
    candidate = Path(value["path"])
    path = (
        candidate.resolve()
        if candidate.is_absolute()
        else (manifest_base / candidate).resolve()
    )
    return _artifact_reference(root, path, kind)


def _prepare_runtime_root(path: Path) -> Path:
    root = path.resolve()
    repository = REPO_ROOT.resolve()
    if root == repository or root.is_relative_to(repository):
        raise _workflow_error(
            "DC_GENERATE_OUTPUT_PROTECTED",
            "Generate runtime output must be outside the repository.",
            artifact_path=root,
        )
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise _workflow_error(
            "DC_GENERATE_OUTPUT_NOT_EMPTY",
            "Generate runtime output must be new or empty.",
            artifact_path=root,
        )
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_prompt(prompt: str | None, prompt_file: Path | None) -> str:
    if (prompt is None) == (prompt_file is None):
        raise _workflow_error(
            "DC_GENERATE_INPUT_INVALID",
            "Provide exactly one of --prompt or --prompt-file.",
        )
    if prompt_file is not None:
        source = prompt_file.resolve()
        if not source.is_file():
            raise _workflow_error(
                "DC_GENERATE_INPUT_MISSING",
                f"Prompt file is missing: {source}",
                artifact_path=source,
            )
        try:
            value = source.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise _workflow_error(
                "DC_GENERATE_INPUT_INVALID",
                "Prompt file must be UTF-8 text.",
                artifact_path=source,
            ) from exc
    else:
        value = prompt or ""
    if not value.strip():
        raise _workflow_error("DC_GENERATE_INPUT_INVALID", "Prompt must not be empty.")
    return value


def _resolve_pdfs(paths: Iterable[Path]) -> tuple[Path, ...]:
    resolved = tuple(Path(path).resolve() for path in paths)
    if len(resolved) > MAX_GENERAL_PDFS:
        raise _workflow_error(
            "DC_GENERATE_INPUT_INVALID",
            f"At most {MAX_GENERAL_PDFS} PDFs may be supplied to one workflow.",
        )
    for path in resolved:
        if not path.is_file():
            raise _workflow_error(
                "DC_GENERATE_INPUT_MISSING",
                f"PDF input is missing: {path}",
                artifact_path=path,
            )
        if path.suffix.lower() != ".pdf":
            raise _workflow_error(
                "DC_GENERATE_INPUT_INVALID",
                f"Document input must use the .pdf extension: {path}",
                artifact_path=path,
            )
    hashes = [_sha256_file(path) for path in resolved]
    if len(hashes) != len(set(hashes)):
        raise _workflow_error(
            "DC_SOURCE_DUPLICATE_CONFLICT",
            "Duplicate PDF bytes are not silently deduplicated.",
        )
    return resolved


def _copy_pdf_inputs(
    paths: tuple[Path, ...],
    inputs_dir: Path,
) -> tuple[Path, ...]:
    copied: list[Path] = []
    for index, source in enumerate(paths, start=1):
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip("-") or "source"
        destination = inputs_dir / f"{index:02d}-{stem}.pdf"
        shutil.copy2(source, destination)
        copied.append(destination)
    return tuple(copied)


def _load_workflow(resume: Path) -> tuple[Path, dict[str, Any]]:
    candidate = resume.resolve()
    manifest_path = candidate / MANIFEST_NAME if candidate.is_dir() else candidate
    if not manifest_path.is_file():
        raise _workflow_error(
            "DC_GENERATE_MANIFEST_MISSING",
            f"Generate workflow manifest is missing: {manifest_path}",
            artifact_path=manifest_path,
        )
    root = manifest_path.parent
    payload = read_json(manifest_path)
    issues = _manifest_issues(payload)
    issues.extend(_input_artifact_issues(root, payload) if not issues else [])
    issues.extend(
        _manifest_artifact_issues(
            root,
            payload,
            kinds={
                "codex_dispatch",
                "codex_workflow_runbook",
                "skillset_execution_plan",
            },
        )
        if not issues
        else []
    )
    issues.extend(_skillset_plan_issues(root, payload) if not issues else [])
    if issues:
        raise _workflow_error(
            "DC_GENERATE_MANIFEST_INVALID",
            "; ".join(issues[:8]),
            artifact_path=manifest_path,
        )
    if Path(payload["runtime_root"]).resolve() != root.resolve():
        raise _workflow_error(
            "DC_GENERATE_RUNTIME_MISMATCH",
            "Workflow manifest runtime_root does not match its current location.",
            artifact_path=manifest_path,
        )
    return root, payload


def _input_artifact_issues(root: Path, payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    contract = payload.get("input_contract")
    if not isinstance(contract, dict):
        return ["input_contract is missing"]
    references = [contract.get("prompt"), *contract.get("pdfs", [])]
    for reference in references:
        if not isinstance(reference, dict):
            issues.append("input artifact reference is malformed")
            continue
        raw = reference.get("path")
        if not isinstance(raw, str):
            issues.append("input artifact path is malformed")
            continue
        candidate = Path(raw)
        path = (
            candidate.resolve()
            if candidate.is_absolute()
            else (root / candidate).resolve()
        )
        if not path.is_file():
            issues.append(f"input artifact is missing: {path}")
            continue
        if reference.get("sha256") != _sha256_file(path):
            issues.append(f"input artifact hash mismatch: {path}")
    return issues


def _manifest_artifact_issues(
    root: Path,
    payload: dict[str, Any],
    *,
    kinds: set[str] | None = None,
) -> list[str]:
    issues: list[str] = []
    references = payload.get("artifacts")
    if not isinstance(references, list):
        return ["workflow artifacts are missing"]
    for reference in references:
        if not isinstance(reference, dict):
            issues.append("workflow artifact reference is malformed")
            continue
        kind = reference.get("kind")
        if kinds is not None and kind not in kinds:
            continue
        raw = reference.get("path")
        if not isinstance(raw, str) or not raw:
            issues.append(f"{kind or 'workflow artifact'} path is malformed")
            continue
        candidate = Path(raw)
        unresolved = candidate if candidate.is_absolute() else root / candidate
        if unresolved.is_symlink():
            issues.append(f"{kind} must not be a symlink: {unresolved}")
            continue
        path = unresolved.resolve()
        expected_scope = (
            "workflow" if path == root or path.is_relative_to(root) else "external"
        )
        if reference.get("scope") != expected_scope:
            issues.append(f"{kind} scope does not match resolved path: {path}")
        if "sha256" in reference:
            if not path.is_file():
                issues.append(f"{kind} artifact is missing: {path}")
            elif reference["sha256"] != _sha256_file(path):
                issues.append(f"{kind} artifact hash mismatch: {path}")
        elif "aggregate_sha256" in reference:
            try:
                fingerprint = _directory_fingerprint(path)
            except DeckCompilerError as exc:
                issues.append(exc.message)
                continue
            if reference["aggregate_sha256"] != fingerprint["aggregate_sha256"]:
                issues.append(f"{kind} directory aggregate mismatch: {path}")
            if reference.get("file_count") != fingerprint["file_count"]:
                issues.append(f"{kind} directory file count mismatch: {path}")
        else:
            issues.append(f"{kind} artifact has no integrity fingerprint")
    return issues


def _skillset_plan_issues(root: Path, payload: dict[str, Any]) -> list[str]:
    references = payload.get("artifacts")
    if not isinstance(references, list):
        return ["skillset execution plan reference is missing"]
    reference = next(
        (
            row
            for row in references
            if isinstance(row, dict) and row.get("kind") == "skillset_execution_plan"
        ),
        None,
    )
    if reference is None:
        return ["skillset execution plan reference is missing"]
    raw_path = reference.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        return ["skillset execution plan path is malformed"]
    candidate = Path(raw_path)
    path = (
        candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    )
    return validate_skillset_execution_plan(
        path,
        expected_workflow_id=payload.get("workflow_id"),
    )


def _sealed_run_issues(root: Path, payload: dict[str, Any]) -> list[str]:
    if payload.get("status") not in {"COMPLETED", "NEEDS_REPAIR"}:
        return []
    references = payload.get("artifacts")
    if not isinstance(references, list):
        return ["sealed Codex run reference is missing"]
    sealed = next(
        (
            reference
            for reference in references
            if isinstance(reference, dict)
            and reference.get("kind") == "sealed_codex_run_manifest"
        ),
        None,
    )
    if sealed is None:
        return ["sealed Codex run reference is missing"]
    candidate = Path(str(sealed["path"]))
    path = (
        candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    )
    try:
        report = validate_codex_run_manifest(
            path,
            expected_workflow_id=payload["workflow_id"],
        )
    except (DeckCompilerError, OSError, ValueError) as exc:
        return [f"sealed Codex run is invalid: {exc}"]
    issues = [f"sealed Codex run: {issue}" for issue in report["issues"]]
    if payload["status"] == "COMPLETED" and not report["completion_ready"]:
        issues.extend(
            f"sealed Codex completion: {issue}" for issue in report["completion_issues"]
        )
        if not report["completion_issues"]:
            issues.append("sealed Codex run is not completion-ready")
    return issues


def _manifest_issues(payload: dict[str, Any]) -> list[str]:
    validator = validator_for(WORKFLOW_SCHEMA)
    issues = [
        f"{'.'.join(str(part) for part in issue.path) or '$'}: {issue.message}"
        for issue in sorted(
            validator.iter_errors(payload),
            key=lambda item: list(item.path),
        )
    ]
    if issues:
        return issues
    value = dict(payload)
    expected = value.pop("manifest_hash")
    actual = content_sha256(value)
    if expected != actual:
        issues.append("manifest_hash does not match canonical manifest content")
    return issues


def _write_workflow_manifest(
    root: Path,
    manifest: dict[str, Any],
) -> None:
    manifest["updated_at"] = _now()
    value = dict(manifest)
    value.pop("manifest_hash", None)
    manifest["manifest_hash"] = content_sha256(value)
    issues = _manifest_issues(manifest)
    if issues:
        raise _workflow_error(
            "DC_GENERATE_MANIFEST_INVALID",
            "; ".join(issues[:8]),
            artifact_path=root / MANIFEST_NAME,
        )
    write_json(root / MANIFEST_NAME, manifest)


def _block_manifest(
    root: Path,
    manifest: dict[str, Any],
    exc: Exception,
) -> None:
    error = (
        exc.to_dict()
        if isinstance(exc, DeckCompilerError)
        else {
            "code": getattr(exc, "code", "DC_GENERATE_FAILED"),
            "stage": "general_generate_workflow",
            "message": str(exc),
            "severity": "error",
            "release_blocking": True,
        }
    )
    manifest["errors"].append(error)
    active = next(
        (
            stage
            for stage in manifest["stages"]
            if stage["status"] in {"RUNNING", "AWAITING_EXTERNAL", "NEEDS_REPAIR"}
        ),
        None,
    )
    if active is not None:
        active["status"] = "BLOCKED"
        active["required_action"] = {
            "code": str(error.get("code", "DC_GENERATE_FAILED")),
            "message": str(error.get("message", exc)),
        }
    manifest["status"] = "BLOCKED"
    _record(manifest, "workflow_blocked", "BLOCKED")
    _sync_artifacts(manifest)
    try:
        _write_workflow_manifest(root, manifest)
    except (DeckCompilerError, OSError, ValueError):
        pass


def _stage(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    return next(stage for stage in manifest["stages"] if stage["stage"] == name)


def _record(manifest: dict[str, Any], event: str, status: str) -> None:
    manifest["history"].append({"timestamp": _now(), "event": event, "status": status})


def _sync_artifacts(manifest: dict[str, Any]) -> None:
    manifest["artifacts"] = [
        artifact for stage in manifest["stages"] for artifact in stage["artifacts"]
    ]


def _current_action(manifest: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            stage["required_action"]
            for stage in manifest["stages"]
            if stage["required_action"] is not None
        ),
        None,
    )


def _result(
    root: Path,
    manifest: dict[str, Any],
    *,
    exit_code: int,
) -> GenerateWorkflowResult:
    return GenerateWorkflowResult(
        workflow_id=manifest["workflow_id"],
        runtime_root=root,
        manifest_path=root / MANIFEST_NAME,
        status=manifest["status"],
        exit_code=exit_code,
        required_action=_current_action(manifest),
    )


def _artifact_reference(
    root: Path,
    path: Path,
    kind: str,
    *,
    directory: bool = False,
) -> dict[str, Any]:
    resolved = path.resolve()
    scope = (
        "workflow" if resolved == root or resolved.is_relative_to(root) else "external"
    )
    reference: dict[str, Any] = {
        "kind": kind,
        "path": _path_value(root, resolved),
        "scope": scope,
    }
    if directory:
        reference.update(_directory_fingerprint(resolved))
    elif resolved.is_file():
        reference["sha256"] = _sha256_file(resolved)
    return reference


def _path_value(root: Path, path: Path) -> str:
    resolved = path.resolve()
    if resolved == root:
        return "."
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    return resolved.as_posix()


def _directory_fingerprint(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise _workflow_error(
            "DC_GENERATE_ARTIFACT_MISSING",
            f"Artifact directory is missing: {root}",
            artifact_path=root,
        )
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise _workflow_error(
                "DC_GENERATE_ARTIFACT_UNSAFE",
                f"Symlinks are forbidden in workflow bundles: {path}",
                artifact_path=path,
            )
        if path.is_file():
            rows.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": _sha256_file(path),
                    "byte_size": path.stat().st_size,
                }
            )
    return {
        "aggregate_sha256": content_sha256(rows),
        "file_count": len(rows),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _workflow_error(
    code: str,
    message: str,
    *,
    artifact_path: Path | None = None,
    remediation_hint: str = (
        "Use the Architect-first Codex workflow and preserve its execution evidence."
    ),
) -> DeckCompilerError:
    return DeckCompilerError(
        code,
        "general_generate_workflow",
        message,
        artifact_path.as_posix() if artifact_path else None,
        remediation_hint=remediation_hint,
    )


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "DISPATCH_NAME",
    "GenerateWorkflowResult",
    "MANIFEST_NAME",
    "MAX_GENERAL_PDFS",
    "PLAN_NAME",
    "RUNBOOK_NAME",
    "resume_generate_workflow",
    "start_generate_workflow",
    "validate_generate_workflow",
]
