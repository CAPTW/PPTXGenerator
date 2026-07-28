"""Compatibility wrapper for PPTX preview rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .render_pptx_preview import (
    DEFAULT_PPTX_PATH,
    DEFAULT_TEMPLATE_OUTPUT_DIR,
    build_parser,
    main,
    render_pptx_preview as _render_pptx_preview,
)


DEFAULT_OUTPUT_DIR = DEFAULT_TEMPLATE_OUTPUT_DIR
DEFAULT_REPORT_PATH = Path("outputs/template_preview_png/render_preview_report.json")


def render_pptx_preview(
    *,
    pptx_path: str | Path = DEFAULT_PPTX_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    report_path: str | Path = DEFAULT_REPORT_PATH,
    renderer: str = "auto",
    dpi: int = 144,
) -> dict[str, Any]:
    return _render_pptx_preview(
        pptx_path=pptx_path,
        output_dir=output_dir,
        manifest_path=report_path,
        backend=renderer,
        dpi=dpi,
    )


__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_PPTX_PATH",
    "DEFAULT_REPORT_PATH",
    "build_parser",
    "main",
    "render_pptx_preview",
]
