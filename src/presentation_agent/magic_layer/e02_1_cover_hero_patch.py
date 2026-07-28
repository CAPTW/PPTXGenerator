"""Cover-hero specific E02.1 patch declaration."""

from __future__ import annotations


def cover_hero_patch_actions() -> list[str]:
    return [
        "bounded_reference_hero_visual_crop",
        "native_diagonal_divider_and_accent_lines",
        "editable_title_subtitle_meta_footer",
        "technical_node_line_overlays",
    ]
