"""E03H text-first lock wrapper."""

from __future__ import annotations

from src.presentation_agent.magic_layer.e02h_text_first_lock import build_e02h_text_first_lock_report, text_first_lock_report_markdown


def build_e03h_text_first_lock_report(reference_definition):
    report = build_e02h_text_first_lock_report(reference_definition)
    report["schema_name"] = "text_first_lock_report"
    return report


__all__ = ["build_e03h_text_first_lock_report", "text_first_lock_report_markdown"]
