"""Text region lift patch helpers for E01.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .benchmark_text_oracle import build_text_region_lift_report, load_benchmark_text_oracle


def run_text_region_lift_patch(text_ledger_path: Path) -> dict[str, Any]:
    oracle = load_benchmark_text_oracle(text_ledger_path)
    text_lift = build_text_region_lift_report(oracle)
    return {
        "schema_name": "e01_1_text_region_lift_patch",
        "status": "passed" if oracle["status"] in {"passed", "partial"} and text_lift["status"] == "passed" else "failed",
        "oracle": oracle,
        "text_lift": text_lift,
        "canva_parity_claimed": False,
    }

