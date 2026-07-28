"""E03H deterministic local reference generation wrappers."""

from __future__ import annotations

from src.presentation_agent.magic_layer.e02h_reference_generator import (
    build_asset_recipe_manifest,
    build_design_intent_trace,
    build_image_prompt,
    build_reference_analysis_report,
    build_reference_visual_richness_report,
    generate_reference_image,
)

__all__ = [
    "build_asset_recipe_manifest",
    "build_design_intent_trace",
    "build_image_prompt",
    "build_reference_analysis_report",
    "build_reference_visual_richness_report",
    "generate_reference_image",
]
