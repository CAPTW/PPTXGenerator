from __future__ import annotations

from typing import Any


def build_region_iou_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [row for row in rows if row.get("region_iou_gate", "passed") != "passed"]
    return {"schema_name": "e03_5_region_iou_summary", "status": "passed" if not failed else "failed", "failed_count": len(failed), "rows": rows}
