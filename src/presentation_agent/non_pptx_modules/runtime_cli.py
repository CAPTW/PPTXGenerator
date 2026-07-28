"""Runtime CLI for phase-by-phase and end-to-end local execution."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .runtime_config import BatchParameters, ProviderSettings, RuntimePaths, RuntimePipelineConfig, load_runtime_config, parse_provider_option_items
from .runtime_pipeline import (
    LEGACY_RUNTIME_STAGE_ORDER,
    StageExecution,
    bootstrap_runtime_config,
    resolve_runtime_workspace,
    run_pipeline,
    run_stage,
    trusted_runtime_execution,
    validate_runtime_state,
)


def _string_path(path: Path | None) -> str | None:
    return None if path is None else path.as_posix()


def _parse_delta_option_args(values: list[str] | None) -> dict[str, str]:
    selections: dict[str, str] = {}
    for item in values or []:
        if "=" not in item:
            raise ValueError(f"delta option selections must use DELTA_ID=OPTION_ID form: {item}")
        delta_id, option_id = item.split("=", 1)
        delta_id = delta_id.strip()
        option_id = option_id.strip()
        if not delta_id or not option_id:
            raise ValueError(f"delta option selections must include both ids: {item}")
        selections[delta_id] = option_id
    return selections


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


def _load_runtime_context(config_path: Path) -> tuple[RuntimePipelineConfig, object]:
    config = load_runtime_config(config_path)
    workspace = resolve_runtime_workspace(config, config_path)
    return config, workspace


def _print_stage_result(result: StageExecution) -> None:
    status = "SKIPPED" if result.skipped else "OK"
    print(f"{status} {result.stage}: {result.detail}")
    for path in result.written:
        print(f"  {path}")


def _default_validation_paths(workspace) -> list[Path]:
    ordered = [
        workspace.state_dir,
        workspace.asset_dir,
        workspace.visual_dir,
        workspace.deck_build_dir,
    ]
    paths: list[Path] = []
    for path in ordered:
        if path.exists() and path not in paths:
            paths.append(path)
    return paths


def _bootstrap(args: argparse.Namespace) -> int:
    config = _build_runtime_config(args)
    result = bootstrap_runtime_config(args.config, config, force=args.force)
    _print_stage_result(result)
    return 0


def _validate_state(args: argparse.Namespace) -> int:
    config, workspace = _load_runtime_context(args.config)
    del config
    paths = args.paths or _default_validation_paths(workspace)
    if not paths:
        raise FileNotFoundError("no runtime artifact directories exist yet; run bootstrap and at least one stage first")
    return validate_runtime_state(paths)


def _run_single_stage(args: argparse.Namespace) -> int:
    config, workspace = _load_runtime_context(args.config)
    with trusted_runtime_execution("legacy-runtime-cli"):
        result = run_stage(
            args.command,
            config,
            workspace,
            force=args.force,
            approved_packet_ids=getattr(args, "approve_packet_id", None),
            approved_fix_ids=getattr(args, "approve_fix_id", None),
            selected_delta_options=_parse_delta_option_args(getattr(args, "select_option", None)),
        )
    _print_stage_result(result)
    return 0


def _run_pipeline(args: argparse.Namespace) -> int:
    config, workspace = _load_runtime_context(args.config)
    with trusted_runtime_execution("legacy-runtime-cli"):
        results = run_pipeline(
            config,
            workspace,
            from_stage=args.from_stage,
            to_stage=args.to_stage,
            force_stages=set(args.force_stage or []),
        )
    for result in results:
        _print_stage_result(result)
    if args.validate_after:
        return validate_runtime_state(_default_validation_paths(workspace))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Runtime orchestration CLI for the presentation agent system.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="Write a runtime config and create the local runtime directory structure.",
    )
    bootstrap_parser.add_argument("--config", required=True, type=Path)
    bootstrap_parser.add_argument("--brief", required=True, type=Path)
    bootstrap_parser.add_argument("--reference-pack", dest="reference_pack", type=Path)
    bootstrap_parser.add_argument("--brand-inputs", dest="brand_inputs", type=Path)
    bootstrap_parser.add_argument("--notes", type=Path)
    bootstrap_parser.add_argument("--state-dir", default="state")
    bootstrap_parser.add_argument("--output-root", default="outputs/runtime")
    bootstrap_parser.add_argument("--gate2-dir")
    bootstrap_parser.add_argument("--orchestration-dir")
    bootstrap_parser.add_argument("--asset-dir")
    bootstrap_parser.add_argument("--visual-dir")
    bootstrap_parser.add_argument("--deck-build-dir")
    bootstrap_parser.add_argument("--slide-ratio", default="16:9")
    bootstrap_parser.add_argument("--render-dpi", type=int, default=144)
    bootstrap_parser.add_argument(
        "--crop-review-loop-limit",
        dest="crop_review_loop_limit",
        type=int,
        default=2,
        help="Bounded crop review loop limit (0-2). Use 0 to skip the review loop and terminate deterministically with the current candidate.",
    )
    bootstrap_parser.add_argument("--max-crop-candidates-per-source", dest="max_crop_candidates_per_source", type=int, default=6)
    bootstrap_parser.add_argument("--provider", default="local-none")
    bootstrap_parser.add_argument("--model")
    bootstrap_parser.add_argument("--endpoint")
    bootstrap_parser.add_argument("--profile")
    bootstrap_parser.add_argument("--provider-option", action="append")
    bootstrap_parser.add_argument("--extended-max-slides", dest="extended_max_slides", type=int, default=8)
    bootstrap_parser.add_argument("--large-deck-max-slides", dest="large_deck_max_slides", type=int, default=6)
    bootstrap_parser.add_argument("--mega-deck-max-slides", dest="mega_deck_max_slides", type=int, default=5)
    bootstrap_parser.add_argument("--blueprint-approved", action="store_true")
    bootstrap_parser.add_argument("--resume-skip-completed", dest="resume_skip_completed", action="store_true", default=True)
    bootstrap_parser.add_argument("--no-resume-skip-completed", dest="resume_skip_completed", action="store_false")
    bootstrap_parser.add_argument("--pptx-name", default="deck.pptx")
    bootstrap_parser.add_argument("--force", action="store_true")

    validate_parser = subparsers.add_parser(
        "validate-state",
        help="Validate canonical state and worker-local manifests for the configured runtime workspace.",
    )
    validate_parser.add_argument("--config", required=True, type=Path)
    validate_parser.add_argument("paths", nargs="*", type=Path)

    for stage in LEGACY_RUNTIME_STAGE_ORDER:
        stage_parser = subparsers.add_parser(stage, help=f"Run the `{stage}` stage against the configured runtime workspace.")
        stage_parser.add_argument("--config", required=True, type=Path)
        stage_parser.add_argument("--force", action="store_true")
        if stage == "apply-approved-fixes":
            stage_parser.add_argument("--approve-packet-id", dest="approve_packet_id", action="append")
            stage_parser.add_argument("--approve-fix-id", dest="approve_fix_id", action="append")
            stage_parser.add_argument("--select-option", dest="select_option", action="append")

    pipeline_parser = subparsers.add_parser(
        "run-pipeline",
        help="Run the local pipeline end to end or across a bounded stage range, resuming from saved state by default.",
    )
    pipeline_parser.add_argument("--config", required=True, type=Path)
    pipeline_parser.add_argument("--from-stage", dest="from_stage", choices=LEGACY_RUNTIME_STAGE_ORDER)
    pipeline_parser.add_argument("--to-stage", dest="to_stage", choices=LEGACY_RUNTIME_STAGE_ORDER)
    pipeline_parser.add_argument("--force-stage", dest="force_stage", action="append", choices=LEGACY_RUNTIME_STAGE_ORDER)
    pipeline_parser.add_argument("--validate-after", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "bootstrap":
        return _bootstrap(args)
    if args.command == "validate-state":
        return _validate_state(args)
    if args.command == "run-pipeline":
        return _run_pipeline(args)
    if args.command in LEGACY_RUNTIME_STAGE_ORDER:
        return _run_single_stage(args)
    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
