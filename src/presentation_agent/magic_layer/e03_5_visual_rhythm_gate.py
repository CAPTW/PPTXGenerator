from __future__ import annotations

from typing import Any


def build_visual_rhythm_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [row for row in rows if row.get("status", "passed") != "passed"]
    return {"schema_name": "e03_5_visual_rhythm_summary", "status": "passed" if not failures else "failed", "critical_rhythm_blocker_count": len(failures), "rows": rows}
