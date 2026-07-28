"""PDFB01 native shape reconstruction baseline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.pdfb01_conversion_strategies import run_strategy


def run_native_shape_reconstruction_baseline(fixture: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    return run_strategy(fixture, output_dir, "native_shape_reconstruction_baseline")
