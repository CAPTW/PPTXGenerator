"""Validate a manual Codex Desktop template-reference image run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


DEFAULT_PROMPT_MANIFEST = Path("outputs/template_image_prompts/template_prompt_manifest.json")
DEFAULT_IMAGE_DIR = Path("outputs/template_images")
DEFAULT_MANIFEST = DEFAULT_IMAGE_DIR / "template_image_manifest.json"
DEFAULT_REPORT = Path("outputs/manual_codex_template_reference_validation.json")


def validate_manual_codex_template_run(
    *,
    prompt_manifest_path: str | Path = DEFAULT_PROMPT_MANIFEST,
    image_dir: str | Path = DEFAULT_IMAGE_DIR,
    manifest_path: str | Path = DEFAULT_MANIFEST,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root) if repo_root else Path.cwd()
    prompt_manifest_file = _resolve_path(prompt_manifest_path, root)
    image_root = _resolve_path(image_dir, root)
    manifest_file = _resolve_path(manifest_path, root)
    failures: list[dict[str, Any]] = []

    prompt_manifest = _load_json_or_failure(prompt_manifest_file, failures, "PROMPT_MANIFEST_UNREADABLE")
    manifest = _load_json_or_failure(manifest_file, failures, "TEMPLATE_IMAGE_MANIFEST_UNREADABLE")
    expected_archetypes = _expected_archetypes(prompt_manifest) if isinstance(prompt_manifest, dict) else []
    image_dimensions: list[dict[str, Any]] = []

    for archetype_id in expected_archetypes:
        image_path = image_root / f"{_safe_file_stem(archetype_id)}.png"
        dimensions = _png_dimensions(image_path)
        if dimensions is None:
            failures.append(
                {
                    "code": "MISSING_REQUIRED_PNG",
                    "archetype_id": archetype_id,
                    "path": _display_path(image_path),
                }
            )
        else:
            image_dimensions.append(
                {
                    "archetype_id": archetype_id,
                    "path": _display_path(image_path),
                    "width_px": dimensions[0],
                    "height_px": dimensions[1],
                }
            )

    manifest_generation_mode = manifest.get("generation_mode") if isinstance(manifest, dict) else None
    if manifest_generation_mode != "manual_codex":
        failures.append(
            {
                "code": "MANIFEST_MODE_NOT_MANUAL_CODEX",
                "expected": "manual_codex",
                "actual": manifest_generation_mode,
                "path": _display_path(manifest_file),
            }
        )

    if isinstance(manifest, dict):
        api_client_implemented = bool(manifest.get("api_client_implemented"))
        repo_does_not_call_api = bool((manifest.get("usage_policy") or {}).get("repo_does_not_call_image_api"))
        if api_client_implemented or not repo_does_not_call_api:
            failures.append(
                {
                    "code": "IMAGE_API_CLIENT_REQUIRED",
                    "api_client_implemented": api_client_implemented,
                    "repo_does_not_call_image_api": repo_does_not_call_api,
                    "path": _display_path(manifest_file),
                }
            )
        for record in manifest.get("images") or []:
            if not isinstance(record, dict):
                failures.append({"code": "MALFORMED_MANIFEST_IMAGE_RECORD", "record": record})
                continue
            image_path_text = record.get("image_output_path")
            if not isinstance(image_path_text, str) or not image_path_text.strip():
                failures.append({"code": "MANIFEST_IMAGE_PATH_MISSING", "archetype_id": record.get("archetype_id")})
                continue
            record_mode = record.get("generation_mode")
            if record_mode != "manual_codex":
                failures.append(
                    {
                        "code": "MANIFEST_IMAGE_MODE_NOT_MANUAL_CODEX",
                        "archetype_id": record.get("archetype_id"),
                        "expected": "manual_codex",
                        "actual": record_mode,
                    }
                )
            image_path = _resolve_path(image_path_text, root)
            dimensions = _png_dimensions(image_path)
            if dimensions is None:
                failures.append(
                    {
                        "code": "MANIFEST_IMAGE_PATH_NOT_FOUND",
                        "archetype_id": record.get("archetype_id"),
                        "path": image_path_text,
                    }
                )
            else:
                record["validated_width_px"] = dimensions[0]
                record["validated_height_px"] = dimensions[1]

    return {
        "schema_name": "manual_codex_template_reference_validation",
        "schema_version": "1.0",
        "status": "failed" if failures else "passed",
        "api_required": any(failure["code"] == "IMAGE_API_CLIENT_REQUIRED" for failure in failures),
        "prompt_manifest_path": _display_path(prompt_manifest_file),
        "image_dir": _display_path(image_root),
        "manifest_path": _display_path(manifest_file),
        "expected_archetypes": expected_archetypes,
        "expected_archetype_count": len(expected_archetypes),
        "manifest_generation_mode": manifest_generation_mode,
        "image_dimensions": image_dimensions,
        "failures": failures,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate manual_codex template reference image ingestion.")
    parser.add_argument("--prompt-manifest", type=Path, default=DEFAULT_PROMPT_MANIFEST)
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = validate_manual_codex_template_run(
        prompt_manifest_path=args.prompt_manifest,
        image_dir=args.image_dir,
        manifest_path=args.manifest,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"WROTE {args.report}")
    print(f"MANUAL_CODEX_TEMPLATE_REFERENCE_VALIDATION {report['status']}")
    if report["failures"]:
        for failure in report["failures"]:
            print(f"MANUAL_CODEX_TEMPLATE_REFERENCE_FAILURE {json.dumps(failure, sort_keys=True, ensure_ascii=True)}")
        return 1
    return 0


def _expected_archetypes(prompt_manifest: dict[str, Any]) -> list[str]:
    entries = prompt_manifest.get("archetype_prompts")
    if not isinstance(entries, list):
        return []
    archetypes = []
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("archetype_id"), str):
            archetypes.append(entry["archetype_id"])
    return archetypes


def _load_json_or_failure(path: Path, failures: list[dict[str, Any]], code: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append({"code": code, "path": _display_path(path), "error": str(exc)})
        return None


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    if not path.exists():
        return None
    try:
        with Image.open(path) as image:
            if image.format != "PNG":
                return None
            return image.size
    except OSError:
        return None


def _resolve_path(path: str | Path, root: Path) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return root / value


def _safe_file_stem(value: str) -> str:
    text = str(value or "").strip().lower()
    keep = [character if character.isalnum() else "_" for character in text]
    return "_".join("".join(keep).split("_")).strip("_") or "template"


def _display_path(path: Path) -> str:
    return str(path.as_posix())


if __name__ == "__main__":
    raise SystemExit(main())
