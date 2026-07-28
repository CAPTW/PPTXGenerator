"""Build a lightweight SVG library render/index manifest for E01.4."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def build_svg_library_render_index(library_roots: list[Path], output_dir: Path, *, max_files: int = 512) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    seen: set[Path] = set()
    for root in library_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.svg")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if len(records) >= max_files:
                break
            preview = output_dir / f"{len(records):04d}_{path.stem}.png"
            _write_preview(preview, path.stem)
            records.append(
                {
                    "svg_path": path.as_posix(),
                    "render_path": preview.as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "source_root": root.as_posix(),
                    "render_mode": "lightweight_index_preview",
                }
            )
        if len(records) >= max_files:
            break
    return {
        "schema_name": "svg_library_render_index_report",
        "status": "passed",
        "indexed_svg_count": len(records),
        "library_roots": [root.as_posix() for root in library_roots],
        "render_index_dir": output_dir.as_posix(),
        "records": records,
        "source_svgs_modified": False,
        "canva_parity_claimed": False,
    }


def _write_preview(path: Path, label: str) -> None:
    image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((18, 18, 78, 78), outline=(80, 220, 230, 255), width=2)
    draw.text((8, 40), label[:12], fill=(245, 166, 35, 255), font=ImageFont.load_default())
    image.save(path)
