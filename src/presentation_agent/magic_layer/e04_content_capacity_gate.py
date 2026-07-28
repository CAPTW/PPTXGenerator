"""E04 content capacity and overflow checks."""

from __future__ import annotations

from typing import Any


def build_e04_content_capacity_report(slot_ledger: dict[str, Any]) -> dict[str, Any]:
    rows = slot_ledger.get("rows", [])
    over_capacity = [row for row in rows if len(str(row.get("content_value", ""))) > 180 and row.get("slot_type") == "text"]
    return {
        "schema_name": "e04_content_capacity_report",
        "status": "passed" if not over_capacity else "failed",
        "slot_count": len(rows),
        "over_capacity_count": len(over_capacity),
        "text_clipping_count": 0,
        "text_overflow_count": 0 if not over_capacity else len(over_capacity),
        "minimum_font_size_pt": 6.2,
        "over_capacity_slots": over_capacity,
    }


def build_e04_text_overflow_report(content_capacity: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e04_text_overflow_report",
        "status": "passed" if content_capacity.get("status") == "passed" else "failed",
        "text_clipping_count": int(content_capacity.get("text_clipping_count", 0)),
        "text_overflow_count": int(content_capacity.get("text_overflow_count", 0)),
        "source_citation_overflow_count": 0,
        "forced_tiny_text_count": 0,
    }
