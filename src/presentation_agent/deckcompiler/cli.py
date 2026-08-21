"""Minimal command-line validation surface for DeckCompiler contracts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .errors import DeckCompilerError
from .manifest_io import read_json
from .manifest_io import write_json
from .orchestration.codex_run import (
    seal_codex_run_manifest,
    validate_codex_run_manifest,
)
from .orchestration.generate import (
    resume_generate_workflow,
    start_generate_workflow,
    validate_generate_workflow,
)
from .orchestration.execution_profiles import (
    DEFAULT_EXECUTION_PROFILE,
    EXECUTION_PROFILE_NAMES,
)
from .orchestration.image_requests import (
    prepare_image_requests,
    validate_image_request_bundle,
)
from .orchestration.quality_acceptance import evaluate_visual_quality_acceptance
from .orchestration.reconstruction_jobs import (
    prepare_reconstruction_jobs,
    validate_reconstruction_job_bundle,
)
from .orchestration.shared_render_qa import finalize_shared_render_qa
from .orchestration.streaming_execution import (
    accept_streaming_image,
    finalize_streaming_images,
    prepare_streaming_execution,
    record_streaming_reconstruction,
    validate_streaming_execution,
)
from .orchestration.phase3_runner import run_phase3
from .pngtopptx_pinning import (
    PinningError,
    build_external_skillset_pin,
    validate_external_skillset_pin,
)
from .pngtopptx_handoff import HandoffError, export_phase4_handoff, validate_handoff
from .qa import CompositeQAError, run_composite_qa, validate_composite_qa
from .repair import FaultFixtureError, apply_fault_fixture, evaluate_fault_detection
from .validation import build_artifact_graph, validate_artifact, validate_run_directory
from .visuals.preparation import prepare_visuals, validate_visual_preparation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deckcompiler", description="Validate PPTX Generator DeckCompiler artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    artifact = subparsers.add_parser("validate", help="Validate one JSON artifact.")
    artifact.add_argument("path", type=Path)
    artifact.add_argument("--schema", required=False)
    artifact.add_argument("--format", choices=("human", "json"), default="human")

    run = subparsers.add_parser("validate-run", help="Validate a complete contract fixture/run directory.")
    run.add_argument("path", type=Path)
    run.add_argument("--format", choices=("human", "json"), default="human")

    graph = subparsers.add_parser("graph", help="Print the artifact provenance graph.")
    graph.add_argument("path", type=Path)
    graph.add_argument("--format", choices=("human", "json"), default="human")

    build = subparsers.add_parser(
        "build-architecture",
        help="Build deterministic Phase 3 intake, strict planning, and creative architecture artifacts.",
    )
    build.add_argument("--config", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)

    generate = subparsers.add_parser(
        "generate",
        help=(
            "Capture a prompt/PDF request for the mandatory Architect-first live "
            "Codex ImageGen-to-PNGtoPPTX workflow."
        ),
    )
    generate.add_argument("--output-dir", type=Path)
    generate.add_argument("--resume", type=Path)
    prompt_group = generate.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file", type=Path)
    generate.add_argument("--pdf", dest="pdfs", type=Path, action="append", default=[])
    generate.add_argument("--audience", default="general professional audience")
    generate.add_argument("--purpose", default="source-grounded presentation")
    generate.add_argument("--language", default="English")
    generate.add_argument("--tone", action="append")
    generate.add_argument(
        "--workflow",
        default="auto",
        help="Optional user hint only; pptx-workflow-architect selects the actual workflow.",
    )
    generate.add_argument(
        "--skill-root",
        type=Path,
        help=(
            "Installed Skill root containing ImageGen and the CAPTW/pngtopptx "
            "companion Skills. The Architect is repository-owned. Defaults to "
            "CODEX_HOME/skills or USERPROFILE/.codex/skills."
        ),
    )
    generate.add_argument(
        "--codex-run-manifest",
        type=Path,
        help="Sealed live Codex run evidence to register while resuming.",
    )
    generate.add_argument(
        "--execution-profile",
        choices=EXECUTION_PROFILE_NAMES,
        default=DEFAULT_EXECUTION_PROFILE,
        help=(
            "Explicit reconstruction runtime profile. ImageGen prompts, Semantic "
            "Sidecars, renderer, compiler, and QA remain identical across profiles."
        ),
    )

    validate_generate = subparsers.add_parser(
        "validate-generate",
        help="Validate a resumable general generate workflow manifest.",
    )
    validate_generate.add_argument("path", type=Path)

    prepare_image_requests_parser = subparsers.add_parser(
        "prepare-image-requests",
        help=(
            "Deterministically derive all ImageGen prompts and Semantic Sidecars "
            "from an approved Architect package without another model call."
        ),
    )
    prepare_image_requests_parser.add_argument("--runtime", type=Path, required=True)

    validate_image_requests_parser = subparsers.add_parser(
        "validate-image-requests",
        help="Validate Blueprint/Design-System lineage for prepared ImageGen requests.",
    )
    validate_image_requests_parser.add_argument("--runtime", type=Path, required=True)

    prepare_streaming_parser = subparsers.add_parser(
        "prepare-streaming-execution",
        help=(
            "Prepare the ImageGen ready queue so each accepted slide can enter "
            "reconstruction before the remaining calls finish."
        ),
    )
    prepare_streaming_parser.add_argument("--runtime", type=Path, required=True)

    accept_streaming_parser = subparsers.add_parser(
        "accept-streaming-image",
        help="Accept one inspected ImageGen PNG and immediately prepare its slide job.",
    )
    accept_streaming_parser.add_argument("--runtime", type=Path, required=True)
    accept_streaming_parser.add_argument("--slide", type=int, required=True)
    accept_streaming_parser.add_argument("--tool-call-id", required=True)
    accept_streaming_parser.add_argument("--queued-at", required=True)
    accept_streaming_parser.add_argument("--started-at", required=True)
    accept_streaming_parser.add_argument("--completed-at", required=True)

    record_streaming_parser = subparsers.add_parser(
        "record-streaming-reconstruction",
        help="Record STARTED or AUTHORING_COMPLETED for one ready reconstruction job.",
    )
    record_streaming_parser.add_argument("--runtime", type=Path, required=True)
    record_streaming_parser.add_argument("--slide", type=int, required=True)
    record_streaming_parser.add_argument(
        "--status", choices=("STARTED", "AUTHORING_COMPLETED"), required=True
    )
    record_streaming_parser.add_argument("--timestamp", required=True)

    finalize_streaming_parser = subparsers.add_parser(
        "finalize-streaming-images",
        help="Seal all per-slide receipts into the canonical ImageGen batch manifest.",
    )
    finalize_streaming_parser.add_argument("--runtime", type=Path, required=True)

    validate_streaming_parser = subparsers.add_parser(
        "validate-streaming-execution",
        help="Validate streaming lineage, completion, and real timing overlap evidence.",
    )
    validate_streaming_parser.add_argument("--runtime", type=Path, required=True)
    validate_streaming_parser.add_argument("--require-complete", action="store_true")
    validate_streaming_parser.add_argument(
        "--require-authoring-complete", action="store_true"
    )
    validate_streaming_parser.add_argument("--require-overlap", action="store_true")

    prepare_reconstruction_jobs_parser = subparsers.add_parser(
        "prepare-reconstruction-jobs",
        help=(
            "Create one hash-bound, fresh-context slide-image-dual-render job "
            "for every accepted ImageGen PNG."
        ),
    )
    prepare_reconstruction_jobs_parser.add_argument(
        "--runtime", type=Path, required=True
    )

    validate_reconstruction_jobs_parser = subparsers.add_parser(
        "validate-reconstruction-jobs",
        help=(
            "Validate reconstruction job lineage and optionally every isolated "
            "worker artifact."
        ),
    )
    validate_reconstruction_jobs_parser.add_argument(
        "--runtime", type=Path, required=True
    )
    validate_reconstruction_jobs_parser.add_argument(
        "--require-authoring-outputs", action="store_true"
    )
    validate_reconstruction_jobs_parser.add_argument(
        "--require-worker-outputs", action="store_true"
    )

    finalize_shared_qa_parser = subparsers.add_parser(
        "finalize-shared-render-qa",
        help=(
            "Close per-slide reconstruction QA receipts from one accepted, "
            "source-mapped shared preview."
        ),
    )
    finalize_shared_qa_parser.add_argument("--runtime", type=Path, required=True)
    finalize_shared_qa_parser.add_argument("--summary", type=Path, required=True)

    validate_visual_quality_parser = subparsers.add_parser(
        "validate-visual-quality",
        help="Apply the final high-fidelity issue policy to official Visual QA evidence.",
    )
    validate_visual_quality_parser.add_argument("--project", type=Path, required=True)
    validate_visual_quality_parser.add_argument("--summary", type=Path, required=True)
    validate_visual_quality_parser.add_argument(
        "--slides", required=True, help="Comma-separated source slide numbers."
    )

    seal_codex_run = subparsers.add_parser(
        "seal-codex-run",
        help="Recompute artifact hashes and seal a live Codex PPTX generation run.",
    )
    seal_codex_run.add_argument("--draft", type=Path, required=True)
    seal_codex_run.add_argument("--output", type=Path, required=True)

    validate_codex_run = subparsers.add_parser(
        "validate-codex-run",
        help="Validate live Architect, ImageGen, PNGtoPPTX, and visual-QA evidence.",
    )
    validate_codex_run.add_argument("path", type=Path)
    validate_codex_run.add_argument("--workflow-id")

    prepare = subparsers.add_parser(
        "prepare-visuals",
        help="Prepare Phase 4B Sidecars, visual DNA, prompts, and pending manifests without image execution.",
    )
    prepare.add_argument("--phase3-run", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)

    validate_preparation = subparsers.add_parser(
        "validate-visual-preparation",
        help="Validate a complete Phase 4B visual-preparation runtime directory.",
    )
    validate_preparation.add_argument("--phase4-run", type=Path, required=True)

    pin_skillset = subparsers.add_parser(
        "pin-pngtopptx-skillset",
        help="Create a read-only provenance pin for the installed CAPTW/pngtopptx SkillSet.",
    )
    pin_skillset.add_argument("--installation-root", type=Path, required=True)
    pin_skillset.add_argument("--source-repository", type=Path)
    pin_skillset.add_argument("--deckcompiler-commit", required=True)
    pin_skillset.add_argument("--output", type=Path, required=True)
    pin_skillset.add_argument("--created-at")
    pin_skillset.add_argument("--timezone", default="Asia/Seoul")

    validate_pin = subparsers.add_parser(
        "validate-pngtopptx-pin",
        help="Recompute the installed SkillSet fingerprint and validate it against a pin.",
    )
    validate_pin.add_argument("--installation-root", type=Path, required=True)
    validate_pin.add_argument("--pin", type=Path, required=True)

    export_handoff = subparsers.add_parser(
        "export-pngtopptx-handoff",
        help="Export a validated Phase 4 bundle to the official PNGtoPPTX project layout.",
    )
    export_handoff.add_argument("--phase4-bundle", type=Path, required=True)
    export_handoff.add_argument("--external-skillset-pin", type=Path, required=True)
    export_handoff.add_argument("--output-dir", type=Path, required=True)
    export_handoff.add_argument("--external-skill-root", type=Path, required=True)
    export_handoff.add_argument("--profile", type=Path, required=True)
    export_handoff.add_argument("--node-path", type=Path, required=True)
    export_handoff.add_argument("--deckcompiler-commit", required=True)
    export_handoff.add_argument("--created-at")
    export_handoff.add_argument("--timezone", default="Asia/Seoul")

    validate_handoff_parser = subparsers.add_parser(
        "validate-pngtopptx-handoff",
        help="Validate a PNGtoPPTX handoff without invoking the external SkillSet.",
    )
    validate_handoff_parser.add_argument("--handoff-dir", type=Path, required=True)

    composite_qa = subparsers.add_parser(
        "qa-composite",
        help="Independently recompute Phase 6 semantic, creative, editability, visual, package, raster, and parity gates.",
    )
    composite_qa.add_argument("--phase4-bundle", type=Path, required=True)
    composite_qa.add_argument("--phase5-bundle", type=Path, required=True)
    composite_qa.add_argument("--output-dir", type=Path, required=True)
    composite_qa.add_argument("--deckcompiler-commit", required=True)
    composite_qa.add_argument("--renders-dir", type=Path)
    composite_qa.add_argument("--renderer-version")
    composite_qa.add_argument("--external-visual-summary", type=Path, required=True)
    composite_qa.add_argument("--external-visual-exit-code", type=int, required=True)
    composite_qa.add_argument("--pptx", type=Path)
    composite_qa.add_argument("--html", type=Path)
    composite_qa.add_argument("--nonbaseline", action="store_true")
    composite_qa.add_argument(
        "--active-output-set",
        choices=("phase5_baseline", "phase6_repaired_baseline"),
        default="phase5_baseline",
    )
    composite_qa.add_argument("--created-at")
    composite_qa.add_argument(
        "--authority-mode",
        choices=("canonical", "runtime"),
        default="canonical",
        help="Use committed canonical authorities or hash the supplied runtime bundles.",
    )

    validate_composite = subparsers.add_parser(
        "validate-composite-qa", help="Validate hash and schema linkage for a complete Phase 6 composite QA directory."
    )
    validate_composite.add_argument("--qa-dir", type=Path, required=True)

    apply_fault = subparsers.add_parser(
        "apply-fault-fixture",
        help="Apply one hash-bound deterministic Phase 6 fault to an isolated upstream project copy.",
    )
    apply_fault.add_argument("--spec", type=Path, required=True)
    apply_fault.add_argument("--project", type=Path, required=True)
    apply_fault.add_argument("--repository-root", type=Path, required=True)
    apply_fault.add_argument("--output", type=Path, required=True)

    detect_fault = subparsers.add_parser(
        "evaluate-fault-detection",
        help="Match an actual failing Composite QA report against the Phase 6 expected-finding contract.",
    )
    detect_fault.add_argument("--composite-report", type=Path, required=True)
    detect_fault.add_argument("--expected-finding", type=Path, required=True)
    detect_fault.add_argument("--fault-application", type=Path, required=True)
    detect_fault.add_argument("--evidence-capsule", type=Path, required=True)
    detect_fault.add_argument("--external-reconciliation", type=Path, required=True)
    detect_fault.add_argument("--official-final-gate-status", required=True)
    detect_fault.add_argument("--renderer-status", required=True)
    detect_fault.add_argument("--deckcompiler-commit", required=True)
    detect_fault.add_argument("--created-at")
    detect_fault.add_argument("--canonical-baseline-unchanged", action="store_true")
    detect_fault.add_argument("--output", type=Path, required=True)

    demo = subparsers.add_parser(
        "demo",
        help="Run the canonical fail-closed DeckCompiler demo and assemble a verified delivery package.",
    )
    demo.add_argument("--config", type=Path, required=True)
    demo.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        try:
            if args.resume is None:
                if args.output_dir is None:
                    raise DeckCompilerError(
                        "DC_GENERATE_INPUT_INVALID",
                        "general_generate_workflow",
                        "--output-dir is required when starting a generate workflow.",
                    )
                if args.codex_run_manifest is not None:
                    raise DeckCompilerError(
                        "DC_GENERATE_INPUT_INVALID",
                        "general_generate_workflow",
                        "--codex-run-manifest requires --resume.",
                    )
                result = start_generate_workflow(
                    output_dir=args.output_dir,
                    prompt=args.prompt,
                    prompt_file=args.prompt_file,
                    pdf_paths=args.pdfs,
                    audience=args.audience,
                    purpose=args.purpose,
                    language=args.language,
                    tone=args.tone or ("professional", "clear"),
                    workflow=args.workflow,
                    skill_root=args.skill_root,
                    execution_profile=args.execution_profile,
                )
            else:
                if (
                    args.output_dir is not None
                    or args.prompt is not None
                    or args.prompt_file is not None
                    or args.pdfs
                    or args.skill_root is not None
                    or args.execution_profile != DEFAULT_EXECUTION_PROFILE
                ):
                    raise DeckCompilerError(
                        "DC_GENERATE_INPUT_INVALID",
                        "general_generate_workflow",
                        "--output-dir, prompt, PDF, Skill-root, and execution-profile inputs cannot be changed while resuming.",
                    )
                result = resume_generate_workflow(
                    resume=args.resume,
                    codex_run_manifest=args.codex_run_manifest,
                )
        except (DeckCompilerError, HandoffError, CompositeQAError, OSError, ValueError) as exc:
            code = getattr(exc, "code", "DC_GENERATE_FAILED")
            print(f"DECKCOMPILER_GENERATE_BLOCKED code={code} message={exc}")
            return 1
        except Exception as exc:  # pragma: no cover - final CLI containment boundary
            print(
                "DECKCOMPILER_GENERATE_BLOCKED "
                f"code=DC_GENERATE_INTERNAL_ERROR message={type(exc).__name__}: {exc}"
            )
            return 1
        action = result.required_action["code"] if result.required_action else "NONE"
        marker = (
            "DECKCOMPILER_GENERATE_COMPLETED"
            if result.status == "COMPLETED"
            else "DECKCOMPILER_GENERATE_NEEDS_REPAIR"
            if result.status == "NEEDS_REPAIR"
            else "DECKCOMPILER_GENERATE_AWAITING"
        )
        print(
            f"{marker} workflow_id={result.workflow_id} status={result.status} "
            f"action={action} manifest={result.manifest_path.as_posix()}"
        )
        return result.exit_code
    if args.command == "validate-generate":
        try:
            report = validate_generate_workflow(args.path)
        except (DeckCompilerError, OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"DECKCOMPILER_GENERATE_MANIFEST_INVALID {exc}")
            return 1
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["valid"] else 1
    if args.command == "prepare-image-requests":
        try:
            result = prepare_image_requests(args.runtime)
        except (DeckCompilerError, OSError, ValueError, json.JSONDecodeError) as exc:
            code = getattr(exc, "code", "DC_IMAGE_REQUEST_PREPARATION_FAILED")
            print(f"DECKCOMPILER_IMAGE_REQUESTS_BLOCKED code={code} message={exc}")
            return 1
        print(
            "DECKCOMPILER_IMAGE_REQUESTS_READY "
            f"workflow_id={result.workflow_id} slides={result.slide_count} "
            f"manifest={result.request_manifest_path.as_posix()}"
        )
        return 0
    if args.command == "validate-image-requests":
        report = validate_image_request_bundle(args.runtime)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["valid"] else 1
    if args.command == "prepare-streaming-execution":
        try:
            result = prepare_streaming_execution(args.runtime)
        except (DeckCompilerError, OSError, ValueError, json.JSONDecodeError) as exc:
            code = getattr(exc, "code", "DC_STREAMING_PREPARATION_FAILED")
            print(f"DECKCOMPILER_STREAMING_BLOCKED code={code} message={exc}")
            return 1
        print(
            "DECKCOMPILER_STREAMING_READY "
            f"workflow_id={result.workflow_id} slides={result.slide_count} "
            f"state={result.state_path.as_posix()}"
        )
        return 0
    if args.command == "accept-streaming-image":
        try:
            result = accept_streaming_image(
                args.runtime,
                slide_number=args.slide,
                tool_call_id=args.tool_call_id,
                queued_at=args.queued_at,
                started_at=args.started_at,
                completed_at=args.completed_at,
            )
        except (DeckCompilerError, OSError, ValueError, json.JSONDecodeError) as exc:
            code = getattr(exc, "code", "DC_STREAMING_IMAGE_ACCEPT_FAILED")
            print(f"DECKCOMPILER_STREAMING_IMAGE_BLOCKED code={code} message={exc}")
            return 1
        print(
            "DECKCOMPILER_STREAMING_IMAGE_READY "
            f"workflow_id={result.workflow_id} slide={result.slide_number} "
            f"job={result.job_path.as_posix()}"
        )
        return 0
    if args.command == "record-streaming-reconstruction":
        try:
            state_path = record_streaming_reconstruction(
                args.runtime,
                slide_number=args.slide,
                status=args.status,
                timestamp=args.timestamp,
            )
        except (DeckCompilerError, OSError, ValueError, json.JSONDecodeError) as exc:
            code = getattr(exc, "code", "DC_STREAMING_RECONSTRUCTION_FAILED")
            print(f"DECKCOMPILER_STREAMING_RECONSTRUCTION_BLOCKED code={code} message={exc}")
            return 1
        print(
            "DECKCOMPILER_STREAMING_RECONSTRUCTION_RECORDED "
            f"slide={args.slide} status={args.status} state={state_path.as_posix()}"
        )
        return 0
    if args.command == "finalize-streaming-images":
        try:
            result = finalize_streaming_images(args.runtime)
        except (DeckCompilerError, OSError, ValueError, json.JSONDecodeError) as exc:
            code = getattr(exc, "code", "DC_STREAMING_FINALIZATION_FAILED")
            print(f"DECKCOMPILER_STREAMING_FINALIZATION_BLOCKED code={code} message={exc}")
            return 1
        print(
            "DECKCOMPILER_STREAMING_IMAGES_FINALIZED "
            f"parallelism={result['max_observed_parallelism']} "
            f"batch={Path(result['batch_manifest_path']).as_posix()}"
        )
        return 0
    if args.command == "validate-streaming-execution":
        report = validate_streaming_execution(
            args.runtime,
            require_complete=args.require_complete,
            require_authoring_complete=args.require_authoring_complete,
            require_overlap=args.require_overlap,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["valid"] else 1
    if args.command == "prepare-reconstruction-jobs":
        try:
            result = prepare_reconstruction_jobs(args.runtime)
        except (DeckCompilerError, OSError, ValueError, json.JSONDecodeError) as exc:
            code = getattr(exc, "code", "DC_RECONSTRUCTION_JOB_PREPARATION_FAILED")
            print(f"DECKCOMPILER_RECONSTRUCTION_JOBS_BLOCKED code={code} message={exc}")
            return 1
        print(
            "DECKCOMPILER_RECONSTRUCTION_JOBS_READY "
            f"workflow_id={result.workflow_id} slides={result.slide_count} "
            f"manifest={result.manifest_path.as_posix()}"
        )
        return 0
    if args.command == "validate-reconstruction-jobs":
        report = validate_reconstruction_job_bundle(
            args.runtime,
            require_authoring_outputs=args.require_authoring_outputs,
            require_worker_outputs=args.require_worker_outputs,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["valid"] else 1
    if args.command == "finalize-shared-render-qa":
        try:
            result = finalize_shared_render_qa(
                args.runtime,
                summary_path=args.summary,
            )
        except (DeckCompilerError, OSError, ValueError, json.JSONDecodeError) as exc:
            code = getattr(exc, "code", "DC_SHARED_RENDER_QA_FAILED")
            print(f"DECKCOMPILER_SHARED_RENDER_QA_BLOCKED code={code} message={exc}")
            return 1
        print(
            "DECKCOMPILER_SHARED_RENDER_QA_READY "
            f"workflow_id={result.workflow_id} slides={result.slide_count} "
            f"summary={result.summary_path.as_posix()}"
        )
        return 0
    if args.command == "validate-visual-quality":
        try:
            slides = sorted(
                {
                    int(value.strip())
                    for value in args.slides.split(",")
                    if value.strip()
                }
            )
            if not slides or any(value <= 0 for value in slides):
                raise ValueError("--slides must contain positive integers")
            report = evaluate_visual_quality_acceptance(
                project=args.project,
                summary_path=args.summary,
                slides=slides,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"DECKCOMPILER_VISUAL_QUALITY_INVALID message={exc}")
            return 1
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["accepted"] else 1
    if args.command == "seal-codex-run":
        try:
            payload = seal_codex_run_manifest(args.draft, args.output)
        except (DeckCompilerError, OSError, ValueError, json.JSONDecodeError) as exc:
            code = getattr(exc, "code", "DC_CODEX_RUN_SEAL_FAILED")
            print(f"DECKCOMPILER_CODEX_RUN_SEAL_BLOCKED code={code} message={exc}")
            return 1
        print(
            "DECKCOMPILER_CODEX_RUN_SEALED "
            f"workflow_id={payload['workflow_id']} status={payload['status']} "
            f"manifest={args.output.resolve().as_posix()}"
        )
        return 0
    if args.command == "validate-codex-run":
        try:
            report = validate_codex_run_manifest(
                args.path,
                expected_workflow_id=args.workflow_id,
            )
        except (DeckCompilerError, OSError, ValueError, json.JSONDecodeError) as exc:
            code = getattr(exc, "code", "DC_CODEX_RUN_INVALID")
            print(f"DECKCOMPILER_CODEX_RUN_INVALID code={code} message={exc}")
            return 1
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["contract_valid"] else 1
    if args.command == "demo":
        from .release.demo import main as demo_main

        return demo_main(["--config", str(args.config), "--output-dir", str(args.output_dir)])
    if args.command == "validate":
        try:
            payload = read_json(args.path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"INVALID unknown path={args.path}\n- INVALID_JSON $: {exc}")
            return 1
        report = validate_artifact(payload, schema_name=args.schema, artifact_path=args.path)
        _print_report(report, args.format)
        return 0 if report.valid else 1
    if args.command == "validate-run":
        report = validate_run_directory(args.path)
        _print_report(report, args.format)
        return 0 if report.valid else 1
    if args.command == "build-architecture":
        try:
            result = run_phase3(args.config, args.output_dir)
        except DeckCompilerError as exc:
            print(
                "DECKCOMPILER_PHASE3_FAILED "
                f"code={exc.code} stage={exc.stage} message={exc.message}"
            )
            return 1
        print(
            "DECKCOMPILER_PHASE3_GO "
            f"run_id={result.run_id} output_dir={result.output_dir.as_posix()}"
        )
        return 0
    if args.command == "prepare-visuals":
        try:
            result = prepare_visuals(args.phase3_run, args.output_dir)
        except DeckCompilerError as exc:
            print(
                "DECKCOMPILER_PHASE4B_FAILED "
                f"code={exc.code} stage={exc.stage} message={exc.message}"
            )
            return 1
        print(
            "DECKCOMPILER_PHASE4B_GO "
            f"sidecars={len(result.sidecar_paths)} prompts={len(result.prompt_paths)} "
            f"output_dir={result.output_dir.as_posix()}"
        )
        return 0
    if args.command == "validate-visual-preparation":
        report = validate_visual_preparation(args.phase4_run)
        if report.valid:
            print(
                "DECKCOMPILER_PHASE4B_VALID "
                f"sidecars={report.checks['semantic_sidecar_count']} "
                f"prompts={report.checks['prompt_artifact_count']}"
            )
            return 0
        print("DECKCOMPILER_PHASE4B_INVALID")
        for issue in report.issues:
            print(f"- {issue}")
        return 1
    if args.command == "pin-pngtopptx-skillset":
        try:
            payload = build_external_skillset_pin(
                args.installation_root,
                source_repository=args.source_repository,
                deckcompiler_commit=args.deckcompiler_commit,
                created_at=args.created_at or datetime.now().astimezone().isoformat(),
                timezone=args.timezone,
            )
            write_json(args.output, payload)
        except (OSError, ValueError, PinningError) as exc:
            print(f"DECKCOMPILER_PHASE5A_PIN_FAILED {exc}")
            return 1
        print(
            "DECKCOMPILER_PHASE5A_PINNED "
            f"mode={payload['pinning_mode']} pin_id={payload['pin_id']} "
            f"aggregate={payload['combined_aggregate_sha256']}"
        )
        return 0
    if args.command == "validate-pngtopptx-pin":
        try:
            result = validate_external_skillset_pin(
                args.installation_root, read_json(args.pin)
            )
        except (OSError, ValueError, PinningError) as exc:
            print(f"DECKCOMPILER_PHASE5A_PIN_INVALID {exc}")
            return 1
        print(
            "DECKCOMPILER_PHASE5A_PIN_VALID "
            f"pin_id={result['pin_id']} aggregate={result['combined_aggregate_sha256']}"
        )
        return 0
    if args.command == "export-pngtopptx-handoff":
        try:
            result = export_phase4_handoff(
                phase4_bundle=args.phase4_bundle,
                external_skillset_pin=args.external_skillset_pin,
                output_dir=args.output_dir,
                deckcompiler_commit=args.deckcompiler_commit,
                external_skill_root=args.external_skill_root,
                profile_path=args.profile,
                node_path=args.node_path,
                created_at=args.created_at or datetime.now().astimezone().isoformat(),
                timezone=args.timezone,
                repository_root=Path(__file__).resolve().parents[3],
            )
        except (OSError, ValueError, HandoffError) as exc:
            print(f"DECKCOMPILER_PHASE5B_HANDOFF_FAILED {exc}")
            return 1
        print(
            "DECKCOMPILER_PHASE5B_HANDOFF_READY "
            f"handoff_dir={result.handoff_root} project_dir={result.project_root} "
            "crop_status=PENDING_OFFICIAL_CROP_PREPARATION"
        )
        return 0
    if args.command == "validate-pngtopptx-handoff":
        try:
            report = validate_handoff(args.handoff_dir)
        except (OSError, ValueError, HandoffError) as exc:
            print(f"DECKCOMPILER_PHASE5B_HANDOFF_INVALID {exc}")
            return 1
        print(
            "DECKCOMPILER_PHASE5B_HANDOFF_VALID "
            f"handoff_id={report['handoff_id']} slides={report['slide_count']}"
        )
        return 0
    if args.command == "qa-composite":
        try:
            result = run_composite_qa(
                args.phase4_bundle,
                args.phase5_bundle,
                args.output_dir,
                deckcompiler_commit=args.deckcompiler_commit,
                renders_dir=args.renders_dir,
                renderer_version=args.renderer_version,
                external_visual_summary=args.external_visual_summary,
                external_visual_exit_code=args.external_visual_exit_code,
                pptx_path=args.pptx,
                html_path=args.html,
                baseline=not args.nonbaseline,
                active_output_set=args.active_output_set,
                created_at=args.created_at,
                authority_mode=args.authority_mode,
            )
        except (CompositeQAError, OSError, ValueError) as exc:
            print(f"DECKCOMPILER_PHASE6_COMPOSITE_BLOCKED {exc}")
            return 1
        print(
            "DECKCOMPILER_PHASE6_COMPOSITE_"
            f"{result.status} run_id={result.run_id} renderer=PowerPoint-{result.renderer_version} "
            f"qa_dir={result.qa_dir.as_posix()}"
        )
        return 0 if result.status == "PASS" else 1
    if args.command == "validate-composite-qa":
        report = validate_composite_qa(args.qa_dir)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["valid"] else 1
    if args.command == "apply-fault-fixture":
        try:
            result = apply_fault_fixture(
                args.spec,
                args.project,
                args.repository_root,
                output_path=args.output,
            )
        except (FaultFixtureError, OSError, ValueError) as exc:
            print(f"DECKCOMPILER_PHASE6_FAULT_INJECTION_BLOCKED {exc}")
            return 1
        print(
            "DECKCOMPILER_PHASE6_FAULT_INJECTED "
            f"fixture_id={result.fixture_id} target={result.target_path} "
            f"before={result.before_sha256} after={result.after_sha256}"
        )
        return 0
    if args.command == "evaluate-fault-detection":
        try:
            report = evaluate_fault_detection(
                read_json(args.composite_report),
                read_json(args.expected_finding),
                read_json(args.fault_application),
                evidence_capsule=read_json(args.evidence_capsule),
                external_reconciliation=read_json(args.external_reconciliation),
                official_final_gate_status=args.official_final_gate_status,
                renderer_status=args.renderer_status,
                canonical_baseline_unchanged=args.canonical_baseline_unchanged,
                created_at=args.created_at,
                deckcompiler_commit=args.deckcompiler_commit,
            )
            write_json(args.output, report)
        except (FaultFixtureError, OSError, ValueError) as exc:
            print(f"DECKCOMPILER_PHASE6_FAILURE_DETECTION_BLOCKED {exc}")
            return 1
        print(
            "DECKCOMPILER_PHASE6_FAILURE_DETECTED "
            f"finding_id={report['detected_finding']['finding_id']} severity={report['detected_finding']['severity']} "
            f"status={report['status']}"
        )
        return 0
    graph = build_artifact_graph(args.path)
    if args.format == "json":
        print(json.dumps(graph, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ARTIFACT_GRAPH run_id={graph['run_id']} nodes={len(graph['nodes'])} edges={len(graph['edges'])}")
        for edge in graph["edges"]:
            print(f"- {edge['from']} -> {edge['to']} ({edge['relation']})")
    return 0


def _print_report(report, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(report.to_human())


if __name__ == "__main__":
    raise SystemExit(main())
