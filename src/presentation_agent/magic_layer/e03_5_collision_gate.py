from __future__ import annotations

from typing import Any


def build_collision_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = sum(int(row.get("object_collision_count", 0) or 0) for row in rows)
    return {"schema_name": "e03_5_collision_summary", "status": "passed" if count == 0 else "failed", "object_collision_count": count, "rows": rows}
