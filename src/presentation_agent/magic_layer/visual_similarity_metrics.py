"""Lightweight visual similarity metrics for D05 reference/render checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat


def compare_images(reference_path: Path, render_path: Path) -> dict[str, Any]:
    reference = Image.open(reference_path).convert("RGB")
    render = Image.open(render_path).convert("RGB").resize(reference.size)
    diff = ImageChops.difference(reference, render)
    stat = ImageStat.Stat(diff)
    mae = sum(stat.mean) / (3 * 255)
    rms = sum(value**2 for value in stat.rms) ** 0.5 / (3**0.5 * 255)
    bbox = diff.getbbox()
    similarity = max(0.0, min(1.0, 1.0 - mae))
    return {
        "schema_name": "reference_render_metrics",
        "reference_size": {"width": reference.width, "height": reference.height},
        "render_size": {"width": render.width, "height": render.height},
        "size_consistent": reference.size == render.size,
        "mean_absolute_error_norm": round(mae, 5),
        "rms_difference_norm": round(rms, 5),
        "nonzero_diff_bbox": list(bbox) if bbox else None,
        "visual_similarity_proxy": round(similarity, 5),
        "metric_notes": "Proxy metrics are used for composition triage; D05 does not require pixel-perfect reproduction.",
    }


def image_is_nonblank(path: Path) -> bool:
    image = Image.open(path).convert("RGB")
    extrema = image.getextrema()
    return any(lo != hi for lo, hi in extrema)

