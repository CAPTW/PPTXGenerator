"""Compile/render helpers for E04.1 patched deck."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def render_e04_1_deck(pptx_path: Path, output_root: Path) -> dict[str, Any]:
    from src.presentation_agent.qa.render_pptx_preview import render_pptx_preview

    raw_dir = output_root / "renders" / "_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    report = render_pptx_preview(pptx_path=pptx_path, output_dir=raw_dir, manifest_path=output_root / "renders" / "render_manifest.json", backend="auto", dpi=144)
    slides = []
    for idx, row in enumerate(report.get("slides", []), start=1):
        source = Path(row.get("rendered_image_path") or "")
        if source.exists():
            target = output_root / "renders" / f"slide-{idx:03d}.png"
            shutil.copy2(source, target)
            row["rendered_image_path"] = target.as_posix()
            slides.append(target)
    report["rendered_slide_count"] = len(slides)
    report["expected_slide_count"] = 16
    report["rendered_paths"] = [path.as_posix() for path in slides]
    return report
