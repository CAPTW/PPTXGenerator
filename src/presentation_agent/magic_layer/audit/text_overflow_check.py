from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def validate_text_overflow(
    *,
    ooxml_audit: dict[str, Any] | None = None,
    text_overflow_report: dict[str, Any] | str | Path | None = None,
    semantic_ledger: dict[str, Any] | str | Path | None = None,
) -> dict[str, Any]:
    report = _load(text_overflow_report)
    ledger = _load(semantic_ledger)
    if "text_overflow_count" in report or "text_clipping_count" in report:
        count = int(report.get("text_overflow_count", 0) or 0) + int(report.get("text_clipping_count", 0) or 0)
        strictness = "STRICT_LEDGER_BASED"
        status = "PASS" if count == 0 else "FAIL"
        limitation = ""
    elif "text_overflow_count" in ledger or "text_clipping_count" in ledger:
        count = int(ledger.get("text_overflow_count", 0) or 0) + int(ledger.get("text_clipping_count", 0) or 0)
        strictness = "STRICT_LEDGER_BASED"
        status = "PASS" if count == 0 else "FAIL"
        limitation = ""
    elif ooxml_audit and ooxml_audit.get("per_slide"):
        count = 0
        strictness = "HEURISTIC_OOXML_BASED"
        status = "NOT_STRICTLY_VALIDATED"
        limitation = "OOXML text exists but B03 does not compute true rendered overflow without a strict ledger."
    else:
        count = 0
        strictness = "UNSUPPORTED_INSUFFICIENT_DATA"
        status = "NOT_STRICTLY_VALIDATED"
        limitation = "No overflow ledger or usable OOXML text geometry was provided."
    return {
        "schema_name": "text_overflow_check.v1",
        "text_overflow_count": count,
        "strictness": strictness,
        "text_overflow_status": status,
        "pass": count == 0,
        "warnings": [] if strictness == "STRICT_LEDGER_BASED" else [limitation],
        "limitation": limitation,
    }


def _load(value: dict[str, Any] | str | Path | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    path = Path(value)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
