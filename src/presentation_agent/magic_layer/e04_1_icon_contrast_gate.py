"""Local contrast and visibility gates for E04.1 icons."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .e03_4_1_cell_visibility_gate import evaluate_icon_cell_visibility


def build_icon_visibility_and_contrast_reports(micro_ledger: dict[str, Any], rendered_paths: list[Path], overlay_path: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    cells = []
    for row in micro_ledger.get("rows", []):
        slide_number = int(row["slide_number"])
        if slide_number - 1 >= len(rendered_paths):
            continue
        cells.append(
            {
                "role_id": row["role"],
                "priority": "P0_REQUIRED_SEMANTIC",
                "size_px": max(16, round(float(row["size_in"]) * 96)),
                "background": "light",
                "bbox_px": row["bbox_px"],
                "render_path": rendered_paths[slide_number - 1].as_posix(),
                "slide_index": 1,
                "slide_number": slide_number,
            }
        )
    visibility = evaluate_icon_cell_visibility(cells, overlay_path=overlay_path) if cells else {"status": "failed", "rows": []}
    visibility["schema_name"] = "semantic_icon_visibility_report"
    visibility["blank_icon_bbox_count"] = visibility.get("blank_icon_cell_count", 0)
    visibility["semantic_raster_icon_count"] = 0
    contrast_failures = [row for row in visibility.get("rows", []) if row.get("mean_contrast", 0) < 30 or not row.get("visible")]
    contrast = {
        "schema_name": "semantic_icon_local_contrast_report",
        "status": "passed" if not contrast_failures else "failed",
        "checked_icon_count": len(visibility.get("rows", [])),
        "contrast_failure_count": len(contrast_failures),
        "rows": visibility.get("rows", []),
    }
    return visibility, contrast
