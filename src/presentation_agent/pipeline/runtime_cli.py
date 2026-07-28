"""CLI for the stage-gated presentation runtime."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from ..non_pptx_modules.runtime_config import (
    BatchParameters,
    ProviderSettings,
    RuntimePaths,
    RuntimePipelineConfig,
    load_runtime_config,
    parse_provider_option_items,
)
from ..non_pptx_modules.runtime_pipeline import (
    bootstrap_runtime_config,
    resolve_runtime_workspace,
    validate_runtime_state,
)
from .executors import build_stage_executors, collect_pipeline_fingerprints
from .orchestrator import PipelineOrchestrator
from .proof_artifact_doctor import (
    inspect_or_normalize_proof_artifact_fleet,
    inspect_or_normalize_proof_artifacts,
    rehearse_proof_artifact_sunset,
)
from .state_store import FingerprintRecord, PipelineStateStore
from .stages import PIPELINE_STAGE_ORDER, PipelineStage, coerce_stage


@dataclass(slots=True)
class PipelineRuntimeSession:
    config_path: Path
    config: RuntimePipelineConfig
    orchestrator: PipelineOrchestrator
    executors: dict[PipelineStage, object]
    fingerprints: list[FingerprintRecord]


def _string_path(path: Path | None) -> str | None:
    return None if path is None else path.as_posix()


def _build_runtime_config(args: argparse.Namespace) -> RuntimePipelineConfig:
    return RuntimePipelineConfig(
        paths=RuntimePaths(
            brief_path=_string_path(args.brief),
            reference_pack_path=_string_path(args.reference_pack),
            brand_inputs_path=_string_path(args.brand_inputs),
            notes_path=_string_path(args.notes),
            state_dir=args.state_dir,
            output_root=args.output_root,
            gate2_dir=args.gate2_dir,
            orchestration_dir=args.orchestration_dir,
            asset_dir=args.asset_dir,
            visual_dir=args.visual_dir,
            deck_build_dir=args.deck_build_dir,
        ),
        slide_ratio=args.slide_ratio,
        render_dpi=args.render_dpi,
        crop_review_loop_limit=args.crop_review_loop_limit,
        max_crop_candidates_per_source=args.max_crop_candidates_per_source,
        blueprint_approved=args.blueprint_approved,
        resume_skip_completed=args.resume_skip_completed,
        pptx_name=args.pptx_name,
        provider=ProviderSettings(
            provider=args.provider,
            model=args.model,
            endpoint=args.endpoint,
            profile=args.profile,
            options=parse_provider_option_items(args.provider_option),
        ),
        batch_parameters=BatchParameters(
            extended_max_slides=args.extended_max_slides,
            large_deck_max_slides=args.large_deck_max_slides,
            mega_deck_max_slides=args.mega_deck_max_slides,
        ),
    )


def build_runtime_session(config_path: str | Path) -> PipelineRuntimeSession:
    resolved_config_path = Path(config_path).resolve()
    config = load_runtime_config(resolved_config_path)
    workspace = resolve_runtime_workspace(config, resolved_config_path)
    store = PipelineStateStore(workspace.state_dir)
    orchestrator = PipelineOrchestrator(store, workspace_root=workspace.base_dir)
    executors = build_stage_executors(config, workspace, orchestrator)
    fingerprints = collect_pipeline_fingerprints(config, workspace)
    return PipelineRuntimeSession(
        config_path=resolved_config_path,
        config=config,
        orchestrator=orchestrator,
        executors=executors,
        fingerprints=fingerprints,
    )


def _ensure_config(args: argparse.Namespace) -> Path:
    config_path = Path(args.config).resolve()
    if config_path.is_file() and not getattr(args, "force_bootstrap", False):
        return config_path
    if getattr(args, "brief", None) is None:
        raise FileNotFoundError(f"runtime config does not exist and --brief was not provided: {config_path}")
    config = _build_runtime_config(args)
    bootstrap_runtime_config(config_path, config, force=True)
    return config_path


def _print_stage_results(result) -> None:
    for stage_result in result.stage_results:
        prefix = "SKIPPED" if stage_result.skipped else stage_result.status
        print(f"{prefix} {stage_result.stage.value}: {stage_result.detail}")


def _run_harness(args: argparse.Namespace, *, resume: bool) -> int:
    config_path = _ensure_config(args) if not resume else Path(args.config).resolve()
    session = build_runtime_session(config_path)
    force_stages = {coerce_stage(stage) for stage in (args.force_stage or [])}
    if resume:
        result = session.orchestrator.resume(
            session.executors,
            to_stage=args.to_stage,
            force_stages=force_stages,
            fingerprint_records=session.fingerprints,
        )
    else:
        result = session.orchestrator.run(
            session.executors,
            from_stage=args.from_stage,
            to_stage=args.to_stage,
            force_stages=force_stages,
            fingerprint_records=session.fingerprints,
        )
    _print_stage_results(result)
    if result.success and result.final_pptx_path:
        print(f"FINAL_PPTX {result.final_pptx_path}")
        return 0
    print(
        f"FINAL_STATUS {result.final_status.value} at {result.final_stage.value}",
        file=sys.stderr,
    )
    return 1


def _bootstrap_only(args: argparse.Namespace) -> int:
    config_path = Path(args.config).resolve()
    config = _build_runtime_config(args)
    result = bootstrap_runtime_config(config_path, config, force=getattr(args, "force_bootstrap", False))
    status = "SKIPPED" if result.skipped else "OK"
    print(f"{status} bootstrap: {result.detail}")
    for path in result.written:
        print(path)
    return 0


def _validate_state(args: argparse.Namespace) -> int:
    config_path = Path(args.config).resolve()
    config = load_runtime_config(config_path)
    workspace = resolve_runtime_workspace(config, config_path)
    paths = args.paths or [workspace.state_dir, workspace.asset_dir, workspace.visual_dir, workspace.deck_build_dir]
    return validate_runtime_state(paths)


def _status(args: argparse.Namespace) -> int:
    session = build_runtime_session(args.config)
    state = session.orchestrator.load_state()
    print(f"CURRENT_STAGE {state.current_stage.value}")
    print(f"RUN_STATUS {state.status.value}")
    if state.invalidated_from_stage is not None:
        print(f"INVALIDATED_FROM {state.invalidated_from_stage.value}")
    final_pptx_path = session.orchestrator.final_pptx_path()
    if final_pptx_path:
        print(f"FINAL_PPTX {final_pptx_path}")
    return 0


def _doctor_proof_artifacts(args: argparse.Namespace) -> int:
    report = inspect_or_normalize_proof_artifacts(args.config, apply=args.apply)
    print(f"STATUS {report.migration_status}")
    print(f"WORKSPACE_CLASSIFICATION {report.workspace_classification}")
    print(f"NORMALIZATION_CLASSIFICATION {report.normalization_classification}")
    print(f"MIGRATION_REQUIRED {str(report.migration_required).lower()}")
    print(f"DRY_RUN {str(report.dry_run).lower()}")
    print(f"REPORT {(Path(args.config).resolve().parent / 'state' / 'proof-artifact-doctor-report.json').as_posix()}")
    for item in report.would_change:
        print(f"WOULD_CHANGE {item}")
    for item in report.applied_changes:
        print(f"APPLIED_CHANGE {item}")
    for item in report.blockers:
        print(f"BLOCKER {item}")
    return 0


def _doctor_proof_artifact_fleet(args: argparse.Namespace) -> int:
    if args.rehearse_sunset:
        if args.apply:
            print("--rehearse-sunset is report-only. Run --apply separately before rehearsal.", file=sys.stderr)
            return 2
        report = rehearse_proof_artifact_sunset(
            args.root,
            report_path=args.report_path,
        )
        print(f"STATUS {report.rehearsal_status.value}")
        print(f"REPORT {Path(report.report_path or '').as_posix() if report.report_path else ''}".rstrip())
        print(
            f"SOURCE_FLEET_REPORT {Path(report.source_fleet_report_path or '').as_posix() if report.source_fleet_report_path else ''}".rstrip()
        )
        print(f"WORKSPACE_COUNT {report.discovered_workspace_count}")
        print(f"REMOVAL_READY {str(report.removal_ready).lower()}")
        print(f"EXIT_CRITERIA_PASSED {str(report.removal_exit_criteria_passed).lower()}")
        for category, count in report.blocker_counts_by_category.items():
            print(f"CATEGORY {category} {count}")
        for classification, count in report.workspace_counts_by_normalization_classification.items():
            print(f"NORMALIZATION_CLASS {classification} {count}")
        for status, count in report.repo_surface_status_counts.items():
            print(f"REPO_SURFACE_STATUS {status} {count}")
        for blocker in report.blockers:
            print(f"BLOCKER {blocker.blocker_category.value} {blocker.blocker_code} {blocker.scope_ref}")
        for workspace in report.workspaces:
            state = "removal-ready" if workspace.removal_ready else "blocked"
            print(
                "WORKSPACE "
                f"{workspace.workspace_root} "
                f"{workspace.workspace_classification} "
                f"{workspace.normalization_classification} "
                f"{state}"
            )
        if args.enforce_removal_ready and not report.removal_ready:
            return 1
        return 0

    report = inspect_or_normalize_proof_artifact_fleet(
        args.root,
        apply=args.apply,
        workspace_classifications=args.classification,
        report_path=args.report_path,
    )
    print(f"STATUS {report.sunset_readiness_status}")
    print(f"REPORT {Path(report.report_path or '').as_posix() if report.report_path else ''}".rstrip())
    print(f"WORKSPACE_COUNT {report.discovered_workspace_count}")
    print(f"STEADY_STATE_ENFORCEMENT_PASSED {str(report.steady_state_enforcement_passed).lower()}")
    for classification, count in report.workspace_counts_by_classification.items():
        print(f"CLASS {classification} {count}")
    for classification, count in report.workspace_counts_by_normalization_classification.items():
        print(f"NORMALIZATION_CLASS {classification} {count}")
    for blocker in report.sunset_blockers:
        print(f"BLOCKER {blocker}")
    for issue in report.discovery_errors:
        print(f"DISCOVERY_ERROR {issue.issue_code} {issue.path}")
    for workspace in report.workspaces:
        print(
            "WORKSPACE "
            f"{workspace.workspace_root} "
            f"{workspace.workspace_classification} "
            f"{workspace.normalization_classification} "
            f"{workspace.migration_status}"
        )
    if args.enforce_registry_only and not report.steady_state_enforcement_passed:
        return 1
    return 0


def _add_runtime_options(parser: argparse.ArgumentParser, *, require_brief: bool) -> None:
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--brief", required=require_brief, type=Path)
    parser.add_argument("--reference-pack", dest="reference_pack", type=Path)
    parser.add_argument("--brand-inputs", dest="brand_inputs", type=Path)
    parser.add_argument("--notes", type=Path)
    parser.add_argument("--state-dir", default="state")
    parser.add_argument("--output-root", default="outputs/runtime")
    parser.add_argument("--gate2-dir")
    parser.add_argument("--orchestration-dir")
    parser.add_argument("--asset-dir")
    parser.add_argument("--visual-dir")
    parser.add_argument("--deck-build-dir")
    parser.add_argument("--slide-ratio", default="16:9")
    parser.add_argument("--render-dpi", type=int, default=144)
    parser.add_argument(
        "--crop-review-loop-limit",
        dest="crop_review_loop_limit",
        type=int,
        default=2,
        help="Bounded crop review loop limit (0-2). Use 0 to skip the review loop and terminate deterministically with the current candidate.",
    )
    parser.add_argument("--max-crop-candidates-per-source", dest="max_crop_candidates_per_source", type=int, default=6)
    parser.add_argument("--provider", default="local-none")
    parser.add_argument("--model")
    parser.add_argument("--endpoint")
    parser.add_argument("--profile")
    parser.add_argument("--provider-option", action="append")
    parser.add_argument("--extended-max-slides", dest="extended_max_slides", type=int, default=8)
    parser.add_argument("--large-deck-max-slides", dest="large_deck_max_slides", type=int, default=6)
    parser.add_argument("--mega-deck-max-slides", dest="mega_deck_max_slides", type=int, default=5)
    parser.add_argument("--blueprint-approved", action="store_true")
    parser.add_argument("--resume-skip-completed", dest="resume_skip_completed", action="store_true", default=True)
    parser.add_argument("--no-resume-skip-completed", dest="resume_skip_completed", action="store_false")
    parser.add_argument("--pptx-name", default="deck.pptx")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage-gated runtime CLI for the presentation agent harness.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser("bootstrap", help="Write or refresh the runtime config without running the harness.")
    _add_runtime_options(bootstrap_parser, require_brief=True)
    bootstrap_parser.add_argument("--force-bootstrap", action="store_true")

    run_parser = subparsers.add_parser("run", help="Run the stage-gated harness from the requested stage range.")
    _add_runtime_options(run_parser, require_brief=False)
    run_parser.add_argument("--force-bootstrap", action="store_true")
    run_parser.add_argument("--from-stage", choices=[stage.value for stage in PIPELINE_STAGE_ORDER])
    run_parser.add_argument("--to-stage", choices=[stage.value for stage in PIPELINE_STAGE_ORDER])
    run_parser.add_argument("--force-stage", action="append", choices=[stage.value for stage in PIPELINE_STAGE_ORDER])

    resume_parser = subparsers.add_parser("resume", help="Resume the harness from the current legal stage.")
    resume_parser.add_argument("--config", required=True, type=Path)
    resume_parser.add_argument("--to-stage", choices=[stage.value for stage in PIPELINE_STAGE_ORDER])
    resume_parser.add_argument("--force-stage", action="append", choices=[stage.value for stage in PIPELINE_STAGE_ORDER])

    status_parser = subparsers.add_parser("status", help="Print the persisted harness state.")
    status_parser.add_argument("--config", required=True, type=Path)

    validate_parser = subparsers.add_parser("validate-state", help="Validate canonical runtime state and worker-local manifests.")
    validate_parser.add_argument("--config", required=True, type=Path)
    validate_parser.add_argument("paths", nargs="*", type=Path)

    doctor_parser = subparsers.add_parser(
        "doctor-proof-artifacts",
        help="Audit or normalize legacy proof-module-manifest compatibility state for shared-proof workspaces.",
    )
    doctor_parser.add_argument("--config", required=True, type=Path)
    doctor_parser.add_argument("--apply", action="store_true")

    fleet_parser = subparsers.add_parser(
        "doctor-proof-artifact-fleet",
        help="Discover, audit, and optionally normalize shared-proof artifact sunset readiness across many runtime workspaces.",
    )
    fleet_parser.add_argument("--root", required=True, type=Path)
    fleet_parser.add_argument("--report-path", type=Path)
    fleet_parser.add_argument("--apply", action="store_true")
    fleet_parser.add_argument(
        "--classification",
        action="append",
        choices=[
            "not-applicable",
            "registry-only",
            "registry-only-clean",
            "registry-only-alias-active",
            "manifest-only",
            "mixed",
            "missing",
        ],
        help="Limit apply mode to the selected workspace classifications. Dry-run still inventories every discovered workspace.",
    )
    fleet_parser.add_argument(
        "--enforce-registry-only",
        action="store_true",
        help="Return a non-zero exit code when direct shared-proof consumers are not in registry-only steady state.",
    )
    fleet_parser.add_argument(
        "--rehearse-sunset",
        action="store_true",
        help="Simulate a future manifest-free release and emit a machine-readable blocker report without mutating workspaces.",
    )
    fleet_parser.add_argument(
        "--enforce-removal-ready",
        action="store_true",
        help="When used with --rehearse-sunset, return a non-zero exit code if any vNext manifest-removal blockers remain.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    raw_args = list(argv or sys.argv[1:])
    legacy_parser = argparse.ArgumentParser(add_help=False)
    legacy_parser.add_argument("--legacy-runtime", action="store_true")
    legacy_args, remaining = legacy_parser.parse_known_args(raw_args)
    if legacy_args.legacy_runtime:
        print("The legacy runtime path is deprecated. Use the stage-gated harness by default.", file=sys.stderr)
        from ..non_pptx_modules.runtime_cli import main as legacy_main

        return legacy_main(remaining)

    parser = build_parser()
    args = parser.parse_args(remaining)
    if args.command == "bootstrap":
        return _bootstrap_only(args)
    if args.command == "run":
        return _run_harness(args, resume=False)
    if args.command == "resume":
        return _run_harness(args, resume=True)
    if args.command == "status":
        return _status(args)
    if args.command == "doctor-proof-artifacts":
        return _doctor_proof_artifacts(args)
    if args.command == "doctor-proof-artifact-fleet":
        return _doctor_proof_artifact_fleet(args)
    if args.command == "validate-state":
        return _validate_state(args)
    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
