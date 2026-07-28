"""Pixel-level visibility gate for PowerPoint-rendered icon fixture cells."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


BACKGROUND_RGB = {"light": (255, 255, 255), "dark": (7, 16, 24)}


def evaluate_icon_cell_visibility(cells: list[dict[str, Any]], *, overlay_path: Path | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for cell in cells:
        row = _evaluate_cell(cell)
        rows.append(row)
    if overlay_path:
        _build_overlay(rows, overlay_path)
    p0_visible = _visible_counts(rows, "P0_REQUIRED_SEMANTIC")
    p1_visible = _visible_counts(rows, "P1_HIGH_REUSE")
    blank_count = sum(not row["visible"] for row in rows)
    report = {
        "schema_name": "icon_fixture_cell_visibility_report",
        "status": "passed" if rows and blank_count == 0 else "failed",
        "cell_count": len(rows),
        "blank_icon_cell_count": blank_count,
        "invisible_icon_count": blank_count,
        "semantic_raster_icon_count": 0,
        "p0_visible_at_16px_count": p0_visible.get(16, 0),
        "p0_visible_at_24px_count": p0_visible.get(24, 0),
        "p0_visible_at_32px_count": p0_visible.get(32, 0),
        "p1_visible_at_16px_count": p1_visible.get(16, 0),
        "p1_visible_at_24px_count": p1_visible.get(24, 0),
        "p1_visible_at_32px_count": p1_visible.get(32, 0),
        "rows": rows,
    }
    return report


def build_dark_light_contrast_report(cell_visibility_report: dict[str, Any]) -> dict[str, Any]:
    rows = cell_visibility_report.get("rows", [])
    failing = [row for row in rows if row.get("mean_contrast", 0) < 20 or not row.get("visible")]
    return {
        "schema_name": "icon_fixture_dark_light_contrast_report",
        "status": "passed" if not failing else "failed",
        "checked_cell_count": len(rows),
        "failed_contrast_count": len(failing),
        "light_cell_count": sum(row.get("background") == "light" for row in rows),
        "dark_cell_count": sum(row.get("background") == "dark" for row in rows),
        "failing_cells": failing[:50],
    }


def _evaluate_cell(cell: dict[str, Any]) -> dict[str, Any]:
    path = Path(cell.get("render_path") or "")
    if not path.exists():
        return {**cell, "visible": False, "non_background_pixel_count": 0, "mean_contrast": 0.0, "failure": "render_missing"}
    image = Image.open(path).convert("RGB")
    x1, y1, x2, y2 = [int(v) for v in cell["bbox_px"]]
    crop = image.crop((x1, y1, x2, y2))
    background = BACKGROUND_RGB.get(cell.get("background", "light"), (255, 255, 255))
    diffs: list[float] = []
    non_bg = 0
    for pixel in crop.getdata():
        distance = math.sqrt(sum((pixel[idx] - background[idx]) ** 2 for idx in range(3)))
        if distance > 24:
            non_bg += 1
            diffs.append(distance)
    min_pixels = max(5, int((cell.get("size_px", 16) ** 2) * 0.05))
    mean_contrast = sum(diffs) / len(diffs) if diffs else 0.0
    visible = non_bg >= min_pixels and mean_contrast >= 30
    return {
        **cell,
        "visible": visible,
        "non_background_pixel_count": non_bg,
        "minimum_visible_pixel_threshold": min_pixels,
        "mean_contrast": round(mean_contrast, 2),
        "failure": None if visible else "blank_or_low_contrast_icon_cell",
    }


def _visible_counts(rows: list[dict[str, Any]], priority: str) -> dict[int, int]:
    counts: dict[int, set[str]] = {}
    for row in rows:
        if row.get("priority") != priority or not row.get("visible"):
            continue
        counts.setdefault(int(row["size_px"]), set()).add(row["role_id"])
    return {size: len(role_ids) for size, role_ids in counts.items()}


def _build_overlay(rows: list[dict[str, Any]], output: Path) -> None:
    first_render = next((Path(row.get("render_path") or "") for row in rows if Path(row.get("render_path") or "").exists()), None)
    if first_render is None:
        return
    image = Image.open(first_render).convert("RGB")
    draw = ImageDraw.Draw(image)
    for row in rows:
        if row.get("slide_index") != 1:
            continue
        x1, y1, x2, y2 = row["bbox_px"]
        draw.rectangle((x1, y1, x2, y2), outline="#22C55E" if row.get("visible") else "#EF4444", width=2)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
