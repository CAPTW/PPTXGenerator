from __future__ import annotations

from typing import Any


def validate_objective_lock(report: dict[str, Any]) -> dict[str, Any]:
    ok = (
        report.get("new_phase") == "recovery_validation_planning"
        and report.get("product_pass") is False
        and report.get("direct_e03_rerun_allowed") is False
    )
    return {"schema": "objective_lock_validator.v1", "pass": ok, "product_pass": False}

