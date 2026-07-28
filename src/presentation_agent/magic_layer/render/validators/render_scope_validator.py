from __future__ import annotations

from typing import Any


def validate_render_scope_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "render_scope_validator.v1",
        "pass": report.get("decision") == "RENDER_SCOPE_ALLOWED" and report.get("pptx_output_allowed") is False,
        "decision": report.get("decision"),
        "product_pass": False,
    }
