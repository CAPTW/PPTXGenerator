"""Source artifact ingestion for E04H."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_SOURCE_FILES = [
    "source_document_graph_v1.json",
    "evidence_bank_v1.json",
    "presentation_plan_v1.json",
    "slide_blueprint_v1.json",
    "source_to_slide_trace_ledger.json",
    "citation_reference_ledger.json",
    "table_data_ledger.json",
    "chart_data_ledger.json",
]


def load_e04h_source_artifacts(source_root: str | Path) -> dict[str, Any]:
    root = Path(source_root)
    missing = [name for name in REQUIRED_SOURCE_FILES if not (root / name).exists()]
    artifacts = {Path(name).stem: _read_json(root / name) for name in REQUIRED_SOURCE_FILES if (root / name).exists()}
    slides = artifacts.get("slide_blueprint_v1", {}).get("slides", [])
    return {
        "schema_name": "source_mode_report",
        "status": "passed" if not missing and len(slides) >= 12 else "failed",
        "source_mode": "EXISTING_REAL_SOURCE_GRAPH",
        "source_root": root.as_posix(),
        "missing": missing,
        "controlled_fixture_created": False,
        "slide_count": len(slides),
        "slides": slides[:16],
        "source_document_graph": artifacts.get("source_document_graph_v1", {}),
        "evidence_bank": artifacts.get("evidence_bank_v1", {}),
        "presentation_plan": artifacts.get("presentation_plan_v1", {}),
        "slide_blueprint": artifacts.get("slide_blueprint_v1", {}),
        "source_to_slide_trace_ledger": artifacts.get("source_to_slide_trace_ledger", {}),
        "citation_reference_ledger": artifacts.get("citation_reference_ledger", {}),
        "table_data_ledger": artifacts.get("table_data_ledger", {}),
        "chart_data_ledger": artifacts.get("chart_data_ledger", {}),
        "canva_parity_claimed": False,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
