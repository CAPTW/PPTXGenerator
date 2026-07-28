"""Compiler adapters for editable template-pack artifacts."""

from .deck_compiler import compile_final_deck, compile_final_deck_from_files
from .deterministic_fallbacks import (
    choose_title_body_slots,
    normalize_card_blocks,
    normalize_chart_data,
    normalize_table_data,
)
from .layout_matcher import build_deck_assembly_plan, build_deck_assembly_plan_from_files
from .template_compiler import compile_template_pack, compile_template_pack_from_files

__all__ = [
    "build_deck_assembly_plan",
    "build_deck_assembly_plan_from_files",
    "compile_final_deck",
    "compile_final_deck_from_files",
    "compile_template_pack",
    "compile_template_pack_from_files",
    "choose_title_body_slots",
    "normalize_card_blocks",
    "normalize_chart_data",
    "normalize_table_data",
]
