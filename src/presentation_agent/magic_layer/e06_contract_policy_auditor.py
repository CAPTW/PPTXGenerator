"""Contract and policy audit for E06."""

from __future__ import annotations

from typing import Any


def audit_contract_and_policy(contract: dict[str, Any], raster: dict[str, Any], text: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "contract_v2_passed": contract.get("status") == "passed",
        "semantic_raster_zero": raster.get("semantic_raster_violation_count", 1) == 0,
        "full_slide_raster_zero": raster.get("full_slide_raster_count", 1) == 0,
        "screenshot_slide_zero": raster.get("screenshot_slide_count", 1) == 0,
        "text_below_6pt_zero": text.get("text_below_6pt_count", 1) == 0,
        "text_overflow_clipping_zero": text.get("text_overflow_count", 1) == 0 and text.get("text_clipping_count", 1) == 0,
    }
    return {
        "schema_name": "e06_contract_and_policy_audit",
        "status": "passed" if all(checks.values()) else "failed",
        "contract_v2_status": contract.get("status"),
        "semantic_raster_violation_count": raster.get("semantic_raster_violation_count", 0),
        "full_slide_raster_count": raster.get("full_slide_raster_count", 0),
        "screenshot_slide_count": raster.get("screenshot_slide_count", 0),
        "text_below_6pt_count": text.get("text_below_6pt_count", 0),
        "text_overflow_count": text.get("text_overflow_count", 0),
        "text_clipping_count": text.get("text_clipping_count", 0),
        "checks": checks,
    }

