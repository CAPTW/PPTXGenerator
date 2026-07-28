from __future__ import annotations

from typing import Any


def validate_replay_report(report: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if report.get("replay_status") not in {"REPLAY_IMPORT_PASS", "REPLAY_IMPORT_PASS_WITH_LIMITATIONS"}:
        failures.append("replay status is not pass")
    if report.get("product_pass") is not False:
        failures.append("replay product_pass must be false")
    return {"schema": "replay_report_validation.v1", "pass": not failures, "failures": failures, "product_pass": False}
