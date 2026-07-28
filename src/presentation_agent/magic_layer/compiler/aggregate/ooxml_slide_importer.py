from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.pipeline.execution.aggregate_report import sha256_file


def source_slide_manifest(source_pptx: list[str | Path]) -> dict[str, Any]:
    return {
        "schema": "aggregate_source_slide_manifest.v1",
        "sources": [
            {"path": str(Path(path)), "sha256": sha256_file(path), "slide_start": 1, "slide_end": 1}
            for path in source_pptx
        ],
        "product_pass": False,
    }
