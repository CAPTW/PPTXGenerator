"""PDF-like object hint extractor for PDFB01 fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def extract_pdf_like_object_hints(fixture_dir: str | Path) -> dict[str, Any]:
    fixture = Path(fixture_dir)
    hints = _read_json(fixture / "source_layer_hint.json")
    return {
        "schema_name": "pdfb01_pdf_object_extractor_report",
        "status": "passed" if hints else "failed",
        "fixture_dir": fixture.as_posix(),
        "text_object_count": len(hints.get("semantic_text_zones", [])),
        "visual_backplate_count": len(hints.get("nonsemantic_visual_backplate_zones", [])),
        "chart_table_object_count": len(hints.get("chart_table_zones", [])),
        "extraction_mode": "pdf_like_layer_hints",
        "canva_parity_claimed": False,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
