"""PDFB01 text lift overlay baseline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.pdfb01_conversion_strategies import run_strategy


def run_text_lift_overlay_baseline(fixture: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    return run_strategy(fixture, output_dir, "text_lift_overlay_baseline")
