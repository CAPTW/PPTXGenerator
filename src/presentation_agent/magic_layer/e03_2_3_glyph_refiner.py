"""Refine medium/complex glyph crops for local vector tracing."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageFilter, ImageOps


VECTOR_CLASSES = {"MEDIUM_MULTI_STROKE", "COMPLEX_MULTI_COMPONENT", "COMPLEX_CONTAINER_GLYPH", "CONTAMINATED_REVIEW_REQUIRED"}


def refine_complex_glyphs(complexity_report: dict[str, Any], output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for icon in complexity_report.get("icons", []):
        if icon.get("complexity_class") not in VECTOR_CLASSES:
            continue
        source = Path(icon.get("normalized_256_path") or icon.get("normalized_crop_path") or icon.get("crop_path", ""))
        if not source.exists():
            continue
        icon_root = output_root / icon["icon_id"]
        icon_root.mkdir(parents=True, exist_ok=True)
        variants = _write_variants(source, icon_root)
        rows.append({**icon, "crop_variants": {key: path.as_posix() for key, path in variants.items()}, "refinement_status": "passed"})
    return {
        "schema_name": "glyph_container_refinement_report",
        "status": "passed",
        "refined_icon_count": len(rows),
        "icons": rows,
    }


def _write_variants(source: Path, icon_root: Path) -> dict[str, Path]:
    image = Image.open(source).convert("RGB")
    gray = ImageOps.grayscale(image)
    bg = int(sorted([gray.getpixel((0, 0)), gray.getpixel((gray.width - 1, 0)), gray.getpixel((0, gray.height - 1)), gray.getpixel((gray.width - 1, gray.height - 1))])[2])
    diff = ImageChops.difference(gray, Image.new("L", gray.size, bg))
    mask = diff.point(lambda p: 255 if p > 20 else 0)
    bbox = mask.getbbox() or (0, 0, image.width, image.height)
    tight = image.crop(bbox)
    padded = ImageOps.expand(tight, border=18, fill="white")
    edge = gray.filter(ImageFilter.FIND_EDGES)
    paths = {
        "glyph_only_tight": icon_root / "glyph_only_tight.png",
        "glyph_with_safe_padding": icon_root / "glyph_with_safe_padding.png",
        "glyph_plus_container": icon_root / "glyph_plus_container.png",
        "high_contrast_mask": icon_root / "high_contrast_mask.png",
        "edge_mask": icon_root / "edge_mask.png",
    }
    tight.save(paths["glyph_only_tight"])
    padded.save(paths["glyph_with_safe_padding"])
    shutil.copy2(source, paths["glyph_plus_container"])
    mask.convert("RGB").save(paths["high_contrast_mask"])
    edge.convert("RGB").save(paths["edge_mask"])
    return paths
