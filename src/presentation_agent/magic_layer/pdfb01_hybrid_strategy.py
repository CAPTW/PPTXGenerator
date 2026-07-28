"""PDFB01 target hybrid backplate plus semantic native strategy."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.pdfb01_conversion_strategies import run_strategy


def run_hybrid_backplate_semantic_native(fixture: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    return run_strategy(fixture, output_dir, "hybrid_backplate_semantic_native")
