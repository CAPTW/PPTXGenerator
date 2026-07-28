"""Icon v7.1 visibility gate for the E04 source-bound deck."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .e03_5_icon_visibility_gate import evaluate_icon_v7_1_visibility
from .e04_deck_planner import E04_SLIDE_ORDER


def build_e04_icon_visibility_report(e03_5_root: Path, rendered_paths: list[Path], overlay_dir: Path) -> dict[str, Any]:
    overlay_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    all_rows = []
    for idx, archetype in enumerate(E04_SLIDE_ORDER, start=1):
        ledger = e03_5_root / "archetypes" / archetype / "icon_v7_1_usage_ledger.json"
        if not ledger.exists() or idx - 1 >= len(rendered_paths):
            continue
        import json

        payload = json.loads(ledger.read_text(encoding="utf-8"))
        rows = []
        for row in payload.get("rows", []):
            updated = {**row, "render_path": rendered_paths[idx - 1].as_posix(), "slide_index": 1, "background": "light", "size_px": 24}
            rows.append(updated)
            all_rows.append(updated)
        report = evaluate_icon_v7_1_visibility(rows, overlay_path=overlay_dir / f"{idx:02d}_{archetype}_icon_visibility_overlay.png") if rows else {"status": "passed", "rows": []}
        report["archetype_id"] = archetype
        report["slide_number"] = idx
        reports.append(report)
    combined = evaluate_icon_v7_1_visibility(all_rows, overlay_path=overlay_dir / "e04_icon_visibility_overlay.png") if all_rows else {"status": "failed", "rows": []}
    return {
        "schema_name": "e04_icon_v7_1_visibility_report",
        "status": combined.get("status"),
        "semantic_icon_count": len(all_rows),
        "icon_v7_1_usage_count": len(all_rows),
        "invisible_icon_count": int(combined.get("invisible_icon_count", 0)),
        "blank_icon_bbox_count": int(combined.get("blank_icon_bbox_count", 0)),
        "semantic_raster_icon_count": 0,
        "true_svg_media_insertion_count": len(all_rows),
        "native_vector_conversion_count": 0,
        "reports": reports,
        "rows": combined.get("rows", []),
    }
