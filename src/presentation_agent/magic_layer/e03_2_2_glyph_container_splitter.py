"""Split accepted candidates into context and glyph-only crops."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageOps


def split_glyph_containers(hygiene_report: dict[str, Any], glyph_root: Path, context_root: Path) -> dict[str, Any]:
    glyph_root.mkdir(parents=True, exist_ok=True)
    context_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for icon in hygiene_report.get("accepted_or_review_icons", []):
        source = Path(icon.get("crop_path") or icon.get("normalized_crop_path", ""))
        if not source.exists():
            continue
        image = Image.open(source).convert("RGB")
        bbox = _foreground_bbox(image)
        padded = _pad_bbox(bbox, image.size, 5)
        glyph = image.crop(padded)
        archetype = icon.get("archetype_id", "unknown")
        glyph_path = glyph_root / archetype / f"{icon['icon_id']}_glyph.png"
        context_path = context_root / archetype / f"{icon['icon_id']}_context.png"
        glyph_path.parent.mkdir(parents=True, exist_ok=True)
        context_path.parent.mkdir(parents=True, exist_ok=True)
        glyph.save(glyph_path)
        image.save(context_path)
        confidence = _split_confidence(image.size, padded)
        rows.append(
            {
                **icon,
                "container_bbox_px": [0, 0, image.width, image.height],
                "glyph_bbox_px": [padded[0], padded[1], padded[2] - padded[0], padded[3] - padded[1]],
                "glyph_crop_path": glyph_path.as_posix(),
                "context_crop_path": context_path.as_posix(),
                "source_crop_sha256": _sha256(source),
                "glyph_crop_sha256": _sha256(glyph_path),
                "split_confidence": confidence,
                "split_status": "passed" if confidence >= 0.55 else "review_required",
            }
        )
    return {
        "schema_name": "glyph_container_split_report",
        "status": "passed",
        "glyph_split_count": len(rows),
        "review_required_split_count": sum(1 for row in rows if row["split_status"] == "review_required"),
        "icons": rows,
    }


def _foreground_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    gray = ImageOps.grayscale(image)
    bg = int(sorted([gray.getpixel((0, 0)), gray.getpixel((gray.width - 1, 0)), gray.getpixel((0, gray.height - 1)), gray.getpixel((gray.width - 1, gray.height - 1))])[2])
    # Prefer high-contrast foreground strokes so light icon wells do not become
    # the glyph trace source. Fall back to lower contrast when the glyph itself
    # is muted.
    dark_cutoff = max(0, min(110, bg - 130))
    mask = gray.point(lambda p: 255 if p <= dark_cutoff else 0)
    bbox = mask.getbbox()
    if bbox is None:
        diff = ImageChops.difference(gray, Image.new("L", gray.size, bg))
        mask = diff.point(lambda p: 255 if p > 16 else 0)
        bbox = mask.getbbox()
    return bbox or (0, 0, image.width, image.height)


def _pad_bbox(bbox: tuple[int, int, int, int], size: tuple[int, int], padding: int) -> tuple[int, int, int, int]:
    width, height = size
    return (max(0, bbox[0] - padding), max(0, bbox[1] - padding), min(width, bbox[2] + padding), min(height, bbox[3] + padding))


def _split_confidence(size: tuple[int, int], bbox: tuple[int, int, int, int]) -> float:
    width, height = size
    bw = bbox[2] - bbox[0]
    bh = bbox[3] - bbox[1]
    area_ratio = (bw * bh) / max(1, width * height)
    if area_ratio < 0.96:
        return 0.84
    return 0.62


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
