from __future__ import annotations

from typing import Any


def build_text_capacity_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    clipping = sum(int(row.get("text_clipping_count", 0) or 0) for row in rows)
    overflow = sum(int(row.get("text_overflow_count", 0) or 0) for row in rows)
    return {"schema_name": "e03_5_text_capacity_summary", "status": "passed" if clipping == 0 and overflow == 0 else "failed", "text_clipping_count": clipping, "text_overflow_count": overflow, "rows": rows}
