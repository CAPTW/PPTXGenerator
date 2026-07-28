"""Render and QA helpers for local presentation artifacts."""

from .diff_template_preview import build_template_diff_report, build_template_diff_report_from_files
from .render_preview import render_pptx_preview

__all__ = ["build_template_diff_report", "build_template_diff_report_from_files", "render_pptx_preview"]
