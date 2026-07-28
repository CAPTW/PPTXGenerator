from __future__ import annotations

from typing import Any


def validate_dimension_report(report: dict[str, Any]) -> dict[str, Any]:
    failures = [row for row in report.get("references", []) if str(row.get("validation_status", "")).startswith("FAIL")]
    return {"schema": "reference_dimension_validator.v1", "pass": not failures, "failure_count": len(failures), "product_pass": False}

