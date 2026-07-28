"""CLI for validating generator contract samples."""

from __future__ import annotations

import argparse
from pathlib import Path

from .generator_contracts import (
    GENERATOR_SCHEMA_FILES,
    discover_generator_contract_samples,
    validate_generator_contract_file,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate generator contract sample artifacts under outputs/."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT / "outputs" / "schema_samples")
    parser.add_argument(
        "--require-schemas",
        action="store_true",
        default=True,
        help="Require at least one valid sample for every generator schema.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()
    search_root = root / "schema_samples" if (root / "schema_samples").is_dir() else root
    samples = discover_generator_contract_samples(search_root)
    if not samples:
        print(f"NO_SAMPLES root={search_root}")
        return 1

    valid_schema_names: set[str] = set()
    unexpected_failures = 0
    expected_failure_count = 0
    for schema_name, path in samples:
        result = validate_generator_contract_file(schema_name, path)
        relative = path.relative_to(search_root) if path.is_relative_to(search_root) else path
        expected_invalid = "invalid" in {part.lower() for part in path.parts} or path.name.startswith("invalid_")
        if result.valid and expected_invalid:
            unexpected_failures += 1
            print(f"UNEXPECTED_PASS schema={schema_name} path={relative}")
            continue
        if not result.valid and expected_invalid:
            expected_failure_count += 1
            first_error = result.errors[0].splitlines()[0] if result.errors else "validation failed"
            print(f"EXPECTED_FAILURE schema={schema_name} path={relative} error={first_error}")
            continue
        if not result.valid:
            unexpected_failures += 1
            first_error = result.errors[0].splitlines()[0] if result.errors else "validation failed"
            print(f"FAIL schema={schema_name} path={relative} error={first_error}")
            continue
        valid_schema_names.add(schema_name)
        print(f"PASS schema={schema_name} path={relative}")

    missing = sorted(set(GENERATOR_SCHEMA_FILES) - valid_schema_names)
    if args.require_schemas and missing:
        unexpected_failures += 1
        print("MISSING_VALID_SAMPLE schemas=" + ",".join(missing))
    if expected_failure_count == 0:
        unexpected_failures += 1
        print("MISSING_INVALID_SAMPLE")
    print(
        "GENERATOR_CONTRACT_VALIDATION "
        f"samples={len(samples)} "
        f"valid_schema_count={len(valid_schema_names)} "
        f"expected_failures={expected_failure_count} "
        f"unexpected_failures={unexpected_failures}"
    )
    return 1 if unexpected_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

