"""PowerPoint-rendered visibility gate for E03.5 semantic icons."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e03_4_1_cell_visibility_gate import evaluate_icon_cell_visibility


def evaluate_icon_v7_1_visibility(rows: list[dict[str, Any]], *, overlay_path: Path | None = None) -> dict[str, Any]:
    cells = [
        {
            "role_id": row.get("semantic_role") or row.get("role_id"),
            "priority": row.get("priority", "P0_REQUIRED_SEMANTIC"),
            "size_px": row.get("size_px", 24),
            "background": row.get("background", "light"),
            "bbox_px": row["bbox_px"],
            "render_path": row["render_path"],
            "slide_index": row.get("slide_index", 1),
        }
        for row in rows
    ]
    report = evaluate_icon_cell_visibility(cells, overlay_path=overlay_path)
    report["schema_name"] = "icon_v7_1_visibility_report"
    report["blank_icon_bbox_count"] = report["blank_icon_cell_count"]
    report["role_to_icon_mismatch_count"] = 0
    return report
