"""E03H visual fidelity wrappers."""

from __future__ import annotations

from src.presentation_agent.magic_layer.e02h_visual_fidelity_gate import (
    build_e02h_visual_fidelity_report,
    build_e02h_visual_richness_retention_report,
    visual_fidelity_report_markdown,
    visual_richness_retention_report_markdown,
)


def build_e03h_visual_fidelity_report(reference_image, rendered_candidate):
    return build_e02h_visual_fidelity_report(reference_image, rendered_candidate)


def build_e03h_visual_richness_retention_report(payload, visual_fidelity):
    return build_e02h_visual_richness_retention_report(payload, visual_fidelity)


__all__ = [
    "build_e03h_visual_fidelity_report",
    "build_e03h_visual_richness_retention_report",
    "visual_fidelity_report_markdown",
    "visual_richness_retention_report_markdown",
]
