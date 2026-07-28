"""Compile the E04-R3 editorial-clean deck."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e04_r2_deck_compiler import compile_e04_r2_art_directed_deck


def compile_e04_r3_deck(binding: dict[str, Any], art_direction: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    """Compile R3 with R2 art direction preserved and visible diagnostic notes disabled."""

    report = compile_e04_r2_art_directed_deck(
        binding,
        art_direction,
        output_dir,
        deck_label="r3",
        show_internal_direction_note=False,
    )
    return {
        **report,
        "schema_name": "e04_r3_deck_compile_report",
        "internal_direction_notes_visible": False,
        "r2_art_direction_preserved": True,
        "canva_parity_claimed": False,
    }
