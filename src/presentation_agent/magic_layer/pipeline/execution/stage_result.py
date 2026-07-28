from __future__ import annotations

from typing import Any


def stage_result(stage_id: str, status: str, *, evidence_paths: list[str] | None = None, limitations: list[str] | None = None, errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema": "pipeline_stage_result.v1",
        "stage_id": stage_id,
        "status": status,
        "evidence_paths": evidence_paths or [],
        "limitations": limitations or [],
        "errors": errors or [],
        "product_pass": False,
    }
