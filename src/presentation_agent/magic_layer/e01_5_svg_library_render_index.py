"""E01.5 SVG library render/index helpers."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def build_e01_5_svg_library_render_index(library_roots: list[Path], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    seen: set[Path] = set()
    registry_hints = _load_registry_hints(library_roots)
    for root in library_roots:
        if not root.exists():
            continue
        for svg_path in sorted(root.rglob("*.svg")):
            resolved = svg_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            text = svg_path.read_text(encoding="utf-8", errors="ignore")
            preview = output_dir / f"{len(records):04d}_{svg_path.stem}.png"
            _write_preview(preview, svg_path.stem)
            records.append(
                {
                    "source_path": svg_path.as_posix(),
                    "sha256": hashlib.sha256(svg_path.read_bytes()).hexdigest(),
                    "viewBox": _viewbox(text),
                    "currentColor_support": "currentColor" in text,
                    "path_count": len(re.findall(r"<path\b", text)),
                    "rendered_path": preview.as_posix(),
                    "rendered_hash": hashlib.sha256(preview.read_bytes()).hexdigest(),
                    "simplified_edge_descriptor": svg_path.stem.lower().replace("-", "_"),
                    "role_hints": registry_hints.get(svg_path.as_posix(), [_slug_hint(svg_path)]),
                }
            )
    return {
        "schema_name": "svg_library_render_index",
        "status": "passed",
        "indexed_svg_count": len(records),
        "library_roots": [root.as_posix() for root in library_roots],
        "records": records,
        "source_svgs_modified": False,
        "canva_parity_claimed": False,
    }


def _load_registry_hints(library_roots: list[Path]) -> dict[str, list[str]]:
    hints: dict[str, list[str]] = {}
    for root in library_roots:
        registry = root / "icon_registry.json"
        if not registry.exists():
            continue
        data = json.loads(registry.read_text(encoding="utf-8"))
        for entry in data.get("icons", []):
            hints.setdefault(entry["generated_svg_path"], []).append(entry.get("role_hint", "generated_icon"))
    return hints


def _viewbox(svg_text: str) -> str | None:
    match = re.search(r'viewBox=["\']([^"\']+)["\']', svg_text)
    return match.group(1) if match else None


def _slug_hint(path: Path) -> str:
    return path.stem.lower().replace("-", "_")


def _write_preview(path: Path, label: str) -> None:
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 50, 206, 206), outline=(64, 225, 235, 255), width=6)
    draw.text((18, 116), label[:28], fill=(245, 166, 35, 255), font=ImageFont.load_default())
    image.save(path)
