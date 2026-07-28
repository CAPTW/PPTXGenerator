from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

from ..pipeline import runtime_cli as _harness_runtime_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Explicit compatibility CLI for legacy proof-artifact migration and sunset rehearsal. "
            "This namespace no longer exposes the full harness runtime surface."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser(
        "doctor-proof-artifacts",
        help="Audit or normalize legacy proof-module-manifest compatibility state for one workspace.",
    )
    doctor_parser.add_argument("--config", required=True, type=Path)
    doctor_parser.add_argument("--apply", action="store_true")

    fleet_parser = subparsers.add_parser(
        "doctor-proof-artifact-fleet",
        help="Discover, rehearse, or normalize shared-proof artifact sunset readiness across many workspaces.",
    )
    fleet_parser.add_argument("--root", required=True, type=Path)
    fleet_parser.add_argument("--report-path", type=Path)
    fleet_parser.add_argument("--apply", action="store_true")
    fleet_parser.add_argument(
        "--classification",
        action="append",
        choices=["not-applicable", "registry-only", "manifest-only", "mixed", "missing"],
        help="Limit apply mode to the selected workspace classifications.",
    )
    fleet_parser.add_argument(
        "--enforce-registry-only",
        action="store_true",
        help="Return a non-zero exit code when direct shared-proof consumers are not in registry-only steady state.",
    )
    fleet_parser.add_argument(
        "--rehearse-sunset",
        action="store_true",
        help="Simulate a future manifest-free release and emit a blocker report without mutating workspaces.",
    )
    fleet_parser.add_argument(
        "--enforce-removal-ready",
        action="store_true",
        help="When used with --rehearse-sunset, return a non-zero exit code if any vNext removal blockers remain.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    warnings.warn(
        "presentation_agent.compat.runtime_cli is deprecated. "
        "Use presentation_agent.runtime_cli or scripts/presentation_agent.py for the harness-first runtime. "
        "This compat namespace is limited to proof-artifact migration and sunset-rehearsal commands.",
        DeprecationWarning,
        stacklevel=2,
    )
    parser = build_parser()
    raw_args = list(argv or sys.argv[1:])
    try:
        args = parser.parse_args(raw_args)
    except SystemExit as exc:
        return int(exc.code)

    if args.command == "doctor-proof-artifacts":
        return _harness_runtime_cli._doctor_proof_artifacts(args)
    if args.command == "doctor-proof-artifact-fleet":
        return _harness_runtime_cli._doctor_proof_artifact_fleet(args)
    parser.error(f"unknown command {args.command!r}")
    return 2


__all__ = ["build_parser", "main"]
