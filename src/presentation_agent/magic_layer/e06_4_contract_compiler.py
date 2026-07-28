"""Compile and render the E06.4 human-tuned contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e06_2_1_contract_compiler_v2 import compile_contract_pptx_v2
from src.presentation_agent.magic_layer.e06_2_contract_compiler import render_contract_deck


def compile_human_tuned_candidate(contract: dict[str, Any], baseline_pptx: Path, output_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    deck = output_root / "human_tuned_candidate" / "harness_v3_e06_4_human_tuned_contract_baseline_candidate.pptx"
    compile_report = compile_contract_pptx_v2(contract, baseline_pptx, deck)
    compile_report["schema_name"] = "human_tuned_compile_report"
    compile_report["human_tuned_candidate_path"] = deck.as_posix()
    render_report = render_contract_deck(deck, output_root, prefix="human_tuned")
    render_report["schema_name"] = "human_tuned_render_report"
    return compile_report, render_report
