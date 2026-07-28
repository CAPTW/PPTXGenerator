from __future__ import annotations

from typing import Any


def build_z_order_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fatal = sum(int(row.get("fatal_inversion_count", 0) or 0) for row in rows)
    failed = [row for row in rows if row.get("z_order_gate", "passed") != "passed"]
    return {"schema_name": "e03_5_z_order_summary", "status": "passed" if fatal == 0 and not failed else "failed", "fatal_inversion_count": fatal, "failed_count": len(failed), "rows": rows}
