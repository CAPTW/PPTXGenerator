from __future__ import annotations

from typing import Any


def validate_source_report(report: dict[str, Any]) -> dict[str, Any]:
    blocked = [row for row in report.get("references", []) if row.get("forbidden_source")]
    return {"schema": "reference_source_validator.v1", "pass": not blocked, "blocked_count": len(blocked), "product_pass": False}

