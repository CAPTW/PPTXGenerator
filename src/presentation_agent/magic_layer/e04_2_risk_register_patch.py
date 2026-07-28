"""Slide 14 risk-register patch for E04.2."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e04_2_comparison_matrix_patch import polish_dense_text_slide


def patch_risk_register_slide(slide) -> dict[str, Any]:
    report = polish_dense_text_slide(slide, slide_number=14, archetype_id="risk_register")
    report["patch_actions"].append("risk_register_readability_polish")
    return report

