"""Ingest manually generated or mock template-reference PNGs into a manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


DEFAULT_PROMPT_MANIFEST = Path("outputs/template_image_prompts/template_prompt_manifest.json")
DEFAULT_IMAGE_DIR = Path("outputs/template_images")
DEFAULT_FIXTURE_DIR = Path("fixtures/template_images")
MANIFEST_FILE = "template_image_manifest.json"
ALLOWED_MODES = {"mock_fixture", "manual_codex", "api_optional_backlog"}


def ingest_template_images(
    *,
    prompt_manifest_path: str | Path = DEFAULT_PROMPT_MANIFEST,
    image_dir: str | Path = DEFAULT_IMAGE_DIR,
    output_manifest_path: str | Path | None = None,
    fixture_dir: str | Path = DEFAULT_FIXTURE_DIR,
    generation_mode: str = "manual_codex",
    allow_mock_fallback: bool = True,
    timestamp: str | None = None,
) -> Path:
    mode = _normalize_mode(generation_mode)
    prompt_manifest_file = Path(prompt_manifest_path)
    prompt_manifest = _load_json(prompt_manifest_file)
    prompt_root = prompt_manifest_file.parent
    output_dir = Path(image_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(output_manifest_path) if output_manifest_path else output_dir / MANIFEST_FILE
    generated_at = timestamp or _timestamp()
    image_records: list[dict[str, Any]] = []
    warnings: list[str] = []

    if mode == "api_optional_backlog":
        warnings.append("api_optional_backlog mode is documented but not implemented; using mock_fixture fallback without API calls.")
        mode_for_images = "mock_fixture"
    else:
        mode_for_images = mode

    for entry in _archetype_entries(prompt_manifest):
        archetype_id = _required_text(entry, "archetype_id")
        prompt_file = prompt_root / _required_text(entry, "prompt_path")
        prompt = prompt_file.read_text(encoding="utf-8")
        image_path = output_dir / f"{_safe_file_stem(archetype_id)}.png"
        source = "manual_codex_png"
        record_mode = mode

        if mode_for_images == "mock_fixture":
            source = _write_mock_image(
                archetype_id=archetype_id,
                prompt=prompt,
                prompt_manifest=prompt_manifest,
                image_path=image_path,
                fixture_dir=Path(fixture_dir),
            )
            record_mode = "mock_fixture"
        elif not _valid_png(image_path):
            message = f"Missing required manual_codex template image for {archetype_id}: {image_path.as_posix()}."
            if allow_mock_fallback:
                warnings.append(message + " Wrote deterministic mock_fixture fallback.")
                source = _write_mock_image(
                    archetype_id=archetype_id,
                    prompt=prompt,
                    prompt_manifest=prompt_manifest,
                    image_path=image_path,
                    fixture_dir=Path(fixture_dir),
                )
                record_mode = "mock_fixture_fallback"
            else:
                warnings.append(message)
                continue

        width_px, height_px = _png_size(image_path)
        image_records.append(
            {
                "archetype_id": archetype_id,
                "prompt_file_path": _display_path(prompt_file),
                "image_output_path": _display_path(image_path),
                "model_name": "codex-desktop-gpt-image-2" if mode == "manual_codex" else "local-mock-fixture",
                "generation_mode": record_mode,
                "timestamp": generated_at,
                "reference_only": True,
                "not_final_slide_background": True,
                "source": source,
                "prompt_sha256": _sha256_text(prompt),
                "width_px": width_px,
                "height_px": height_px,
            }
        )

    if mode == "mock_fixture":
        warnings.append("mock_fixture mode used; images are deterministic placeholders or copied local fixtures.")
    if mode == "manual_codex" and not warnings:
        warnings.append("manual_codex mode used; repository ingested existing PNGs and did not call an image API.")
    if not image_records:
        raise ValueError("no template images were ingested; provide PNGs or allow mock fallback")

    manifest = {
        "schema_name": "template_image_manifest",
        "schema_version": "1.0",
        "source_prompt_manifest_path": _display_path(prompt_manifest_file),
        "generation_mode": mode,
        "available_modes": ["mock_fixture", "manual_codex", "api_optional_backlog"],
        "api_client_implemented": False,
        "timestamp": generated_at,
        "reference_only": True,
        "usage_policy": {
            "gpt_image_outputs_are_design_references_only": True,
            "do_not_use_as_final_slide_backgrounds": True,
            "final_deck_must_remain_editable": True,
            "repo_does_not_call_image_api": True,
        },
        "images": image_records,
        "warnings": warnings,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return manifest_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest template reference PNGs produced by Codex Desktop or local mock fixtures.")
    parser.add_argument("--prompt-manifest", type=Path, default=DEFAULT_PROMPT_MANIFEST)
    parser.add_argument("--image-dir", "--output-dir", dest="image_dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--output-manifest", type=Path, default=None)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--mode", choices=sorted(ALLOWED_MODES), default=os.environ.get("TEMPLATE_IMAGE_MODE", "manual_codex"))
    parser.add_argument("--no-mock-fallback", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        manifest = ingest_template_images(
            prompt_manifest_path=args.prompt_manifest,
            image_dir=args.image_dir,
            output_manifest_path=args.output_manifest,
            fixture_dir=args.fixture_dir,
            generation_mode=args.mode,
            allow_mock_fallback=not args.no_mock_fallback,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"INGEST_TEMPLATE_IMAGES_FAILED {exc}")
        return 1
    print(f"WROTE {manifest}")
    return 0


def _write_mock_image(
    *,
    archetype_id: str,
    prompt: str,
    prompt_manifest: dict[str, Any],
    image_path: Path,
    fixture_dir: Path,
) -> str:
    fixture = fixture_dir / f"{_safe_file_stem(archetype_id)}.png"
    if fixture.exists():
        image_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixture, image_path)
        return _display_path(fixture)

    image = Image.new("RGB", (1600, 900), _palette(archetype_id, prompt)[0])
    draw = ImageDraw.Draw(image)
    palette = _palette(archetype_id, prompt)
    font_large = _font(58)
    font_medium = _font(32)
    font_small = _font(24)

    draw.rounded_rectangle((64, 58, 1536, 842), radius=24, fill=palette[1], outline=palette[2], width=4)
    draw.rectangle((64, 58, 1536, 154), fill=palette[2])
    draw.text((102, 86), "TEMPLATE REFERENCE ONLY", fill=palette[4], font=font_medium)
    draw.text((102, 190), _label(archetype_id), fill=palette[3], font=font_large)
    draw.text((104, 270), "TITLE", fill=palette[3], font=font_medium)
    draw.rounded_rectangle((102, 326, 688, 442), radius=16, fill=palette[0], outline=palette[2], width=3)
    draw.text((136, 362), "CHART", fill=palette[3], font=font_medium)
    draw.rounded_rectangle((724, 326, 1498, 442), radius=16, fill=palette[0], outline=palette[2], width=3)
    draw.text((758, 362), "TABLE", fill=palette[3], font=font_medium)
    for index in range(3):
        left = 102 + (index * 466)
        draw.rounded_rectangle((left, 486, left + 416, 700), radius=18, fill=palette[0], outline=palette[2], width=3)
        draw.text((left + 30, 522), "KPI", fill=palette[3], font=font_medium)
        draw.rectangle((left + 30, 590, left + 354, 610), fill=palette[2])
        draw.rectangle((left + 30, 632, left + 272, 652), fill=palette[2])
    draw.rounded_rectangle((102, 732, 1498, 796), radius=12, fill=palette[0], outline=palette[2], width=2)
    draw.text((132, 750), "FOOTER", fill=palette[3], font=font_small)
    draw.text((1230, 748), prompt_manifest.get("prompt_model_target", "GPT-Image-2"), fill=palette[3], font=font_small)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(image_path, format="PNG")
    return "generated_mock_fixture"


def _valid_png(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with Image.open(path) as image:
            return image.format == "PNG"
    except OSError:
        return False


def _png_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _palette(archetype_id: str, prompt: str) -> tuple[tuple[int, int, int], ...]:
    digest = hashlib.sha256(f"{archetype_id}\n{prompt}".encode("utf-8")).digest()
    accent = (72 + digest[0] % 100, 82 + digest[1] % 90, 92 + digest[2] % 90)
    pale = (236 + digest[3] % 14, 238 + digest[4] % 12, 240 + digest[5] % 10)
    ink = (28, 34, 42)
    reverse = (248, 250, 252)
    return pale, reverse, accent, ink, reverse


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _archetype_entries(prompt_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    entries = prompt_manifest.get("archetype_prompts")
    if not isinstance(entries, list) or not entries:
        raise ValueError("template prompt manifest must contain archetype_prompts")
    return [entry for entry in entries if isinstance(entry, dict)]


def _required_text(entry: dict[str, Any], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"template prompt manifest entry missing {key}")
    return value.strip()


def _normalize_mode(value: str) -> str:
    mode = str(value or "").strip().lower()
    if mode not in ALLOWED_MODES:
        raise ValueError(f"unsupported template image mode: {value}")
    return mode


def _timestamp() -> str:
    fixed = os.environ.get("TEMPLATE_IMAGE_GENERATION_TIMESTAMP")
    if fixed:
        return fixed
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_file_stem(value: str) -> str:
    text = str(value or "").strip().lower()
    keep = [character if character.isalnum() else "_" for character in text]
    return "_".join("".join(keep).split("_")).strip("_") or "template"


def _display_path(path: Path) -> str:
    return str(path.as_posix())


def _label(archetype_id: str) -> str:
    return archetype_id.replace("_", " ").upper()


if __name__ == "__main__":
    raise SystemExit(main())
