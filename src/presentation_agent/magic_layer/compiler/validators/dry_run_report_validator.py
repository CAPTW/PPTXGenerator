from __future__ import annotations

from typing import Any


DECISIONS = {
    "DRY_RUN_READY",
    "DRY_RUN_READY_WITH_WARNINGS",
    "DRY_RUN_BLOCKED_INVALID_INPUT",
    "DRY_RUN_BLOCKED_UNSUPPORTED_REQUIRED_INSTRUCTION",
    "DRY_RUN_BLOCKED_COMPILE_POLICY",
    "DRY_RUN_BLOCKED_PROTECTED_ARTIFACT_POLICY",
    "DRY_RUN_INSUFFICIENT_EVIDENCE",
}


def validate_dry_run_report(report: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if report.get("schema") != "dry_run_compile_report.v1":
        failures.append("schema must be dry_run_compile_report.v1")
    if report.get("decision") not in DECISIONS:
        failures.append("invalid dry-run decision")
    if report.get("product_pass") is not False:
        failures.append("product_pass must be false")
    if report.get("pptx_generated") is not False:
        failures.append("pptx_generated must be false in C01")
    if report.get("render_generated") is not False:
        failures.append("render_generated must be false in C01")
    if "B03_native_validation_gate" not in report.get("downstream_gates", []):
        failures.append("B03 downstream gate required")
    return {"schema": "dry_run_report_validation.v1", "pass": not failures, "failures": failures}
