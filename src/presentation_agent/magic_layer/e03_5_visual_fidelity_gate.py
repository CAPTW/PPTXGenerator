from __future__ import annotations

from typing import Any


def build_visual_fidelity_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [row for row in rows if row.get("visual_fidelity_gate", "passed") != "passed"]
    return {"schema_name": "e03_5_visual_fidelity_summary", "status": "passed" if not failed else "failed", "failed_count": len(failed), "rows": rows}
