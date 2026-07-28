"""Normalize glyph-only crops for matching and SVG tracing."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


def normalize_glyph_crops(split_report: dict[str, Any], output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for icon in split_report.get("icons", []):
        source = Path(icon["glyph_crop_path"])
        if not source.exists():
            continue
        normalized_paths = {}
        for size in (128, 256):
            out = output_root / icon.get("archetype_id", "unknown") / f"{icon['icon_id']}_{size}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            _normalize_one(source, out, size)
            normalized_paths[size] = out.as_posix()
        rows.append(
            {
                **icon,
                "normalized_128_path": normalized_paths[128],
                "normalized_256_path": normalized_paths[256],
                "normalized_glyph_sha256": _sha256(Path(normalized_paths[256])),
                "normalization_status": "passed",
            }
        )
    return {
        "schema_name": "normalized_glyph_crop_manifest",
        "status": "passed",
        "normalized_glyph_crop_count": len(rows),
        "icons": rows,
    }


def _normalize_one(source: Path, output: Path, size: int) -> None:
    image = Image.open(source).convert("RGB")
    image = ImageOps.contain(image, (size - 24, size - 24), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), "white")
    canvas.paste(image, ((size - image.width) // 2, (size - image.height) // 2))
    canvas.save(output)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
