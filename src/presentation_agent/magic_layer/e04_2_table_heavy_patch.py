"""Slide 11 table-heavy patch for E04.2."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e04_2_comparison_matrix_patch import polish_dense_text_slide


def patch_table_heavy_slide(slide) -> dict[str, Any]:
    report = polish_dense_text_slide(slide, slide_number=11, archetype_id="table_heavy")
    report["patch_actions"].append("table_heavy_grid_readability_polish")
    return report

