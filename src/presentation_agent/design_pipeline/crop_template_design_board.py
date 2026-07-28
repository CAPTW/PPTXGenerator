"""Crop manually generated template design boards into inspectable regions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BOARD_MANIFEST = Path("outputs/template_design_board/template_design_board_manifest.json")
DEFAULT_BOARD_IMAGE = Path("outputs/template_design_board/creative_academic_design_board.png")
DEFAULT_CROP_CONFIG = Path("design_prompts/creative_academic_template_board.crop_config.json")
DEFAULT_OUTPUT_DIR = Path("outputs/template_design_board/crops")
DEFAULT_OUTPUT_MANIFEST = Path("outputs/template_design_board/design_board_crop_manifest.json")
COORDINATE_SYSTEM = "normalized_0_1"


def crop_template_design_board(
    *,
    board_manifest_path: str | Path = DEFAULT_BOARD_MANIFEST,
    board_image_path: str | Path = DEFAULT_BOARD_IMAGE,
    crop_config_path: str | Path = DEFAULT_CROP_CONFIG,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    output_manifest_path: str | Path = DEFAULT_OUTPUT_MANIFEST,
) -> Path:
    board_manifest_file = Path(board_manifest_path)
    board_image = Path(board_image_path)
    crop_config = Path(crop_config_path)
    output = Path(output_manifest_path)
    output_root = Path(output_dir)

    if not board_image.exists():
        raise FileNotFoundError(f"template design board image not found: {board_image.as_posix()}; generate it manually in Codex Desktop and save it at this path")
    if not board_manifest_file.exists():
        raise FileNotFoundError(f"template design board manifest not found: {board_manifest_file.as_posix()}; run npm run ingest:template-design-board first")
    board_manifest = _load_json(board_manifest_file)
    if board_manifest.get("generation_mode") != "manual_codex":
        raise ValueError("template design board manifest must record generation_mode=manual_codex")

    with Image.open(board_image) as image:
        image = image.convert("RGB")
        width, height = image.size
        if not crop_config.exists():
            manifest = _empty_manifest(board_manifest, board_image, "manual_config_missing", f"crop config missing: {crop_config.as_posix()}; no crops were generated")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
            return output

        config = _load_json(crop_config)
        crop_entries = _validate_config(config)
        output_root.mkdir(parents=True, exist_ok=True)
        crops: list[dict[str, Any]] = []
        for entry in crop_entries:
            box, warnings = _pixel_box(entry, width, height)
            crop_id = str(entry["crop_id"])
            crop_path = output_root / f"{crop_id}.png"
            image.crop(box).save(crop_path, format="PNG")
            crops.append(
                {
                    "crop_id": crop_id,
                    "crop_role": entry["crop_role"],
                    "expected_content": entry["expected_content"],
                    "path": _display_path(crop_path),
                    "x": float(entry["x"]),
                    "y": float(entry["y"]),
                    "w": float(entry["w"]),
                    "h": float(entry["h"]),
                    "coordinate_system": COORDINATE_SYSTEM,
                    "warnings": warnings,
                }
            )

    manifest = {
        "schema_name": "design_board_crop_manifest",
        "schema_version": "1.0",
        "board_image_path": _display_path(board_image),
        "prompt_id": board_manifest["prompt_id"],
        "crop_mode": "manual_config",
        "crop_count": len(crops),
        "coordinate_system": COORDINATE_SYSTEM,
        "crop_config_path": _display_path(crop_config),
        "crops": crops,
        "warnings": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crop the single Codex Desktop design-board PNG into inspectable reference regions.")
    parser.add_argument("--board-manifest", type=Path, default=DEFAULT_BOARD_MANIFEST)
    parser.add_argument("--board-image", type=Path, default=DEFAULT_BOARD_IMAGE)
    parser.add_argument("--crop-config", type=Path, default=DEFAULT_CROP_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-manifest", type=Path, default=DEFAULT_OUTPUT_MANIFEST)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = crop_template_design_board(
            board_manifest_path=args.board_manifest,
            board_image_path=args.board_image,
            crop_config_path=args.crop_config,
            output_dir=args.output_dir,
            output_manifest_path=args.output_manifest,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"CROP_TEMPLATE_DESIGN_BOARD_FAILED {exc}")
        return 1
    print(f"WROTE {output}")
    return 0


def _empty_manifest(board_manifest: dict[str, Any], board_image: Path, crop_mode: str, warning: str) -> dict[str, Any]:
    return {
        "schema_name": "design_board_crop_manifest",
        "schema_version": "1.0",
        "board_image_path": _display_path(board_image),
        "prompt_id": board_manifest["prompt_id"],
        "crop_mode": crop_mode,
        "crop_count": 0,
        "coordinate_system": COORDINATE_SYSTEM,
        "crops": [],
        "warnings": [warning],
    }


def _validate_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    if config.get("coordinate_system") != COORDINATE_SYSTEM:
        raise ValueError(f"crop config coordinate_system must be {COORDINATE_SYSTEM}")
    crops = config.get("crops")
    if not isinstance(crops, list) or not crops:
        raise ValueError("crop config must contain a non-empty crops array")
    required = {"crop_id", "crop_role", "expected_content", "x", "y", "w", "h"}
    seen: set[str] = set()
    for entry in crops:
        if not isinstance(entry, dict):
            raise ValueError("crop config entries must be objects")
        missing = sorted(required - set(entry))
        if missing:
            raise ValueError(f"crop config entry missing fields: {', '.join(missing)}")
        crop_id = str(entry["crop_id"])
        if crop_id in seen:
            raise ValueError(f"duplicate crop_id in crop config: {crop_id}")
        seen.add(crop_id)
        for key in ("x", "y", "w", "h"):
            value = float(entry[key])
            if value < 0 or value > 1:
                raise ValueError(f"crop {crop_id} field {key} must be normalized 0..1")
        if float(entry["w"]) <= 0 or float(entry["h"]) <= 0:
            raise ValueError(f"crop {crop_id} must have positive w and h")
    return crops


def _pixel_box(entry: dict[str, Any], width: int, height: int) -> tuple[tuple[int, int, int, int], list[str]]:
    x = float(entry["x"])
    y = float(entry["y"])
    w = float(entry["w"])
    h = float(entry["h"])
    warnings = []
    if x + w > 1 or y + h > 1:
        warnings.append("CROP_BOX_CLAMPED_TO_BOARD_BOUNDS")
    left = max(0, min(width - 1, round(x * width)))
    top = max(0, min(height - 1, round(y * height)))
    right = max(left + 1, min(width, round((x + w) * width)))
    bottom = max(top + 1, min(height, round((y + h) * height)))
    return (left, top, right, bottom), warnings


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
