"""Ingest a single manually generated Codex Desktop design-board PNG."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BOARD_IMAGE = Path("outputs/template_design_board/creative_academic_design_board.png")
DEFAULT_PROMPT_MANIFEST = Path("design_prompts/prompt_manifest.json")
DEFAULT_OUTPUT_MANIFEST = Path("outputs/template_design_board/template_design_board_manifest.json")
DEFAULT_PROMPT_ID = "creative_academic_template_board_v1"
EXPECTED_OUTER_RATIO = "3:2"
EXPECTED_INTERNAL_SLIDE_RATIO = "16:9"
EXPECTED_NUMERIC_RATIO = 3 / 2
RATIO_TOLERANCE = 0.04


def ingest_template_design_board(
    *,
    board_image_path: str | Path = DEFAULT_BOARD_IMAGE,
    prompt_manifest_path: str | Path = DEFAULT_PROMPT_MANIFEST,
    output_manifest_path: str | Path = DEFAULT_OUTPUT_MANIFEST,
    prompt_id: str = DEFAULT_PROMPT_ID,
) -> Path:
    board_image = Path(board_image_path)
    prompt_manifest_file = Path(prompt_manifest_path)
    output_manifest = Path(output_manifest_path)
    prompt_manifest = _load_json(prompt_manifest_file)
    prompt_entry = _find_prompt(prompt_manifest, prompt_id)
    prompt_file = _resolve_prompt_file(prompt_entry["prompt_file"], prompt_manifest_file)

    if not board_image.exists():
        raise FileNotFoundError(
            f"template design board image not found: {board_image.as_posix()}; "
            "generate it manually in Codex Desktop and save it at this path"
        )
    width, height = _image_size(board_image)
    ratio = width / max(1, height)
    warnings = _warnings_for_ratio(ratio)
    warnings.append("manual_codex mode used; repository ingested an existing PNG and did not call an Image API.")

    manifest = {
        "schema_name": "template_design_board_manifest",
        "schema_version": "1.0",
        "generation_mode": "manual_codex",
        "prompt_id": prompt_entry["prompt_id"],
        "prompt_file": _display_path(prompt_file),
        "board_image_path": _display_path(board_image),
        "board_mode": "single_design_board",
        "expected_output_type": prompt_entry["expected_output_type"],
        "expected_outer_ratio": EXPECTED_OUTER_RATIO,
        "expected_internal_slide_ratio": prompt_entry.get("internal_slide_ratio") or EXPECTED_INTERNAL_SLIDE_RATIO,
        "design_balance": prompt_entry["design_balance"],
        "expected_zones": prompt_entry["expected_zones"],
        "expected_slide_types": prompt_entry.get("expected_slide_types", []),
        "image_width": width,
        "image_height": height,
        "image_ratio": round(ratio, 6),
        "premium_design_candidate": True,
        "reference_only": True,
        "usage_policy": {
            "gpt_image_output_is_design_reference_only": True,
            "do_not_insert_board_image_as_full_slide_background": True,
            "repo_does_not_call_image_api": True,
            "final_deck_must_remain_editable": True,
        },
        "images": [
            {
                "archetype_id": "design_board",
                "prompt_file_path": _display_path(prompt_file),
                "image_output_path": _display_path(board_image),
                "model_name": "codex-desktop-gpt-image-2",
                "generation_mode": "manual_codex",
                "reference_only": True,
                "not_final_slide_background": True,
                "width_px": width,
                "height_px": height,
            }
        ],
        "warnings": warnings,
    }
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return output_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest a single Codex Desktop GPT-Image-2 template design board PNG.")
    parser.add_argument("--board-image", type=Path, default=DEFAULT_BOARD_IMAGE)
    parser.add_argument("--prompt-manifest", type=Path, default=DEFAULT_PROMPT_MANIFEST)
    parser.add_argument("--output-manifest", type=Path, default=DEFAULT_OUTPUT_MANIFEST)
    parser.add_argument("--prompt-id", default=DEFAULT_PROMPT_ID)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = ingest_template_design_board(
            board_image_path=args.board_image,
            prompt_manifest_path=args.prompt_manifest,
            output_manifest_path=args.output_manifest,
            prompt_id=args.prompt_id,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"INGEST_TEMPLATE_DESIGN_BOARD_FAILED {exc}")
        return 1
    print(f"WROTE {output}")
    return 0


def _find_prompt(prompt_manifest: dict[str, Any], prompt_id: str) -> dict[str, Any]:
    prompts = prompt_manifest.get("prompts")
    if not isinstance(prompts, list) or not prompts:
        raise ValueError("prompt_manifest.json must contain a non-empty prompts array")
    for entry in prompts:
        if isinstance(entry, dict) and entry.get("prompt_id") == prompt_id:
            _validate_prompt_entry(entry)
            return entry
    raise ValueError(f"prompt_id not found in prompt manifest: {prompt_id}")


def _validate_prompt_entry(entry: dict[str, Any]) -> None:
    required = [
        "prompt_id",
        "prompt_file",
        "design_balance",
        "expected_output_type",
        "generation_mode",
        "internal_slide_ratio",
        "expected_zones",
        "expected_slide_types",
    ]
    missing = [key for key in required if key not in entry]
    if missing:
        raise ValueError(f"prompt manifest entry missing required fields: {', '.join(missing)}")
    if entry["expected_output_type"] != "single_3_2_design_board":
        raise ValueError("prompt manifest expected_output_type must be single_3_2_design_board")
    if entry["generation_mode"] != "manual_codex":
        raise ValueError("prompt manifest generation_mode must be manual_codex")
    if entry["internal_slide_ratio"] != EXPECTED_INTERNAL_SLIDE_RATIO:
        raise ValueError("prompt manifest internal_slide_ratio must be 16:9")
    if not isinstance(entry["expected_zones"], list) or not entry["expected_zones"]:
        raise ValueError("prompt manifest expected_zones must be a non-empty array")
    if not isinstance(entry["expected_slide_types"], list) or not entry["expected_slide_types"]:
        raise ValueError("prompt manifest expected_slide_types must be a non-empty array")


def _resolve_prompt_file(prompt_file_value: str, prompt_manifest_file: Path) -> Path:
    prompt_file = Path(prompt_file_value)
    candidates = [prompt_file]
    if not prompt_file.is_absolute():
        candidates = [REPO_ROOT / prompt_file, prompt_manifest_file.parent / prompt_file]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"prompt file not found: {prompt_file_value}")


def _image_size(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return image.size
    except OSError as exc:
        raise ValueError(f"could not read template design board image dimensions from {path.as_posix()}: {exc}") from exc


def _warnings_for_ratio(ratio: float) -> list[str]:
    delta = abs(ratio - EXPECTED_NUMERIC_RATIO)
    if delta > RATIO_TOLERANCE:
        return [
            f"OUTER_RATIO_MISMATCH: expected approximately 3:2 ({EXPECTED_NUMERIC_RATIO:.4f}) but image ratio is {ratio:.4f}."
        ]
    return []


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
