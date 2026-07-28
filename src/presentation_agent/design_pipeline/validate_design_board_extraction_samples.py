"""Validate design-board extraction contract samples and optional real artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema.exceptions import ValidationError

from ..generator_contracts import validate_generator_contract_file
from .extract_design_board_codex_contract import EXTRACTION_CONTRACTS, validate_design_board_extraction_files


REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_ROOT = REPO_ROOT / "outputs" / "schema_samples"
DESIGN_EXTRACTION_DIR = REPO_ROOT / "outputs" / "design_extraction"


def validate_design_board_extraction_samples(*, include_actual: bool = False) -> int:
    failures: list[dict[str, Any]] = []
    valid_count = 0
    expected_failure_count = 0

    for contract in EXTRACTION_CONTRACTS:
        valid_path = SAMPLE_ROOT / "valid" / f"{contract.schema_name}.json"
        result = validate_generator_contract_file(contract.schema_name, valid_path)
        if result.valid:
            valid_count += 1
            print(f"PASS schema={contract.schema_name} path={_rel(valid_path)}")
        else:
            failures.append({"code": "VALID_SAMPLE_FAILED", "schema": contract.schema_name, "path": _rel(valid_path), "errors": result.errors})
            print(f"FAIL schema={contract.schema_name} path={_rel(valid_path)}")

        invalid_path = SAMPLE_ROOT / "invalid" / f"invalid_{contract.schema_name}.json"
        invalid_result = validate_generator_contract_file(contract.schema_name, invalid_path)
        if invalid_result.valid:
            failures.append({"code": "INVALID_SAMPLE_PASSED", "schema": contract.schema_name, "path": _rel(invalid_path)})
            print(f"UNEXPECTED_PASS schema={contract.schema_name} path={_rel(invalid_path)}")
        else:
            expected_failure_count += 1
            first_error = invalid_result.errors[0].splitlines()[0] if invalid_result.errors else "validation failed"
            print(f"EXPECTED_FAILURE schema={contract.schema_name} path={_rel(invalid_path)} error={first_error}")

    if include_actual and DESIGN_EXTRACTION_DIR.exists():
        artifact_report = validate_design_board_extraction_files(artifacts_dir=DESIGN_EXTRACTION_DIR, require_all=False)
        for result in artifact_report["results"]:
            if result["status"] == "failed":
                failures.append({"code": "REAL_ARTIFACT_FAILED", **result})
            print(
                "ARTIFACT "
                f"schema={result['schema_name']} "
                f"status={result['status']} "
                f"path={result['path']}"
            )

    print(
        "DESIGN_BOARD_EXTRACTION_VALIDATION "
        f"mode={'samples_plus_optional_actual' if include_actual else 'samples'} "
        f"valid_samples={valid_count} "
        f"expected_failures={expected_failure_count} "
        f"unexpected_failures={len(failures)}"
    )
    if failures:
        print("DESIGN_BOARD_EXTRACTION_VALIDATION_FAILURES " + json.dumps(failures, sort_keys=True, ensure_ascii=True))
    return 1 if failures else 0


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(validate_design_board_extraction_samples())
