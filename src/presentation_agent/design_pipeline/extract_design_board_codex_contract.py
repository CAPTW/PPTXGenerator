"""Contracts for Codex-assisted design-board extraction.

This module does not call external models. It centralizes artifact paths,
schema names, extraction prompt references, and validation helpers for the
manual Codex Desktop design-board extraction workflow.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from jsonschema.exceptions import ValidationError

from ..generator_contracts import (
    validateExtractedComponentLibrary,
    validateExtractedDesignBoardCodex,
    validateExtractedSlideArchetypes,
    validateExtractedStyleTokens,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DESIGN_EXTRACTION_DIR = Path("outputs/design_extraction")
CODEX_EXTRACTION_PROMPT_DOC = Path("docs/CODEX_DESIGN_BOARD_EXTRACTION_PROMPT.md")
CANONICAL_PROMPT_FILE = Path("design_prompts/creative_academic_template_board.prompt.txt")
CANONICAL_PROMPT_MANIFEST = Path("design_prompts/prompt_manifest.json")
TEMPLATE_DESIGN_BOARD_MANIFEST = Path("outputs/template_design_board/template_design_board_manifest.json")


@dataclass(frozen=True, slots=True)
class DesignBoardExtractionContract:
    schema_name: str
    artifact_path: Path
    validator: Callable[[dict[str, Any]], dict[str, Any]]


EXTRACTION_CONTRACTS: tuple[DesignBoardExtractionContract, ...] = (
    DesignBoardExtractionContract(
        "extracted_design_board_codex",
        DESIGN_EXTRACTION_DIR / "extracted_design_board.codex.json",
        validateExtractedDesignBoardCodex,
    ),
    DesignBoardExtractionContract(
        "extracted_slide_archetypes",
        DESIGN_EXTRACTION_DIR / "extracted_slide_archetypes.json",
        validateExtractedSlideArchetypes,
    ),
    DesignBoardExtractionContract(
        "extracted_component_library",
        DESIGN_EXTRACTION_DIR / "extracted_component_library.json",
        validateExtractedComponentLibrary,
    ),
    DesignBoardExtractionContract(
        "extracted_style_tokens",
        DESIGN_EXTRACTION_DIR / "extracted_style_tokens.json",
        validateExtractedStyleTokens,
    ),
)


def extraction_prompt_context() -> dict[str, Any]:
    return {
        "prompt_doc": _display_path(CODEX_EXTRACTION_PROMPT_DOC),
        "canonical_prompt_file": _display_path(CANONICAL_PROMPT_FILE),
        "prompt_manifest": _display_path(CANONICAL_PROMPT_MANIFEST),
        "template_design_board_manifest": _display_path(TEMPLATE_DESIGN_BOARD_MANIFEST),
        "output_artifacts": {
            contract.schema_name: _display_path(contract.artifact_path)
            for contract in EXTRACTION_CONTRACTS
        },
        "policy": {
            "external_model_calls_in_repo": False,
            "create_pptx": False,
            "rasterize_slides": False,
            "board_image_is_reference_only": True,
            "final_pptx_must_remain_editable": True,
        },
    }


def validate_design_board_extraction_artifact(schema_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    for contract in EXTRACTION_CONTRACTS:
        if contract.schema_name == schema_name:
            return contract.validator(payload)
    raise ValueError(f"unknown design-board extraction schema: {schema_name}")


def validate_design_board_extraction_files(
    *,
    artifacts_dir: str | Path = DESIGN_EXTRACTION_DIR,
    require_all: bool = False,
) -> dict[str, Any]:
    root = Path(artifacts_dir)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for contract in EXTRACTION_CONTRACTS:
        path = root / contract.artifact_path.name
        if not path.exists():
            result = {
                "schema_name": contract.schema_name,
                "path": _display_path(path),
                "status": "missing",
            }
            results.append(result)
            if require_all:
                failures.append({**result, "error": "required artifact missing"})
            continue
        try:
            payload = _load_json(path)
            contract.validator(payload)
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            result = {
                "schema_name": contract.schema_name,
                "path": _display_path(path),
                "status": "failed",
                "error": str(exc).splitlines()[0],
            }
            results.append(result)
            failures.append(result)
            continue
        results.append(
            {
                "schema_name": contract.schema_name,
                "path": _display_path(path),
                "status": "passed",
            }
        )
    return {
        "schema_name": "design_board_extraction_validation_report",
        "schema_version": "1.0",
        "status": "failed" if failures else "passed",
        "require_all": require_all,
        "results": results,
        "failures": failures,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Codex-assisted design-board extraction artifacts.")
    parser.add_argument("--artifacts-dir", type=Path, default=DESIGN_EXTRACTION_DIR)
    parser.add_argument("--require-all", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = validate_design_board_extraction_files(
        artifacts_dir=args.artifacts_dir,
        require_all=args.require_all,
    )
    for result in report["results"]:
        print(
            "DESIGN_BOARD_EXTRACTION "
            f"schema={result['schema_name']} "
            f"status={result['status']} "
            f"path={result['path']}"
        )
    return 1 if report["status"] == "failed" else 0


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
