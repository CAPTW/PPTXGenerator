from __future__ import annotations

from typing import Any

from ..stage_registry import STAGE_ORDER


def validate_stage_registry(registry: dict[str, Any]) -> dict[str, Any]:
    ids = {stage.get("stage_id") for stage in registry.get("stages", [])}
    failures = [f"missing stage {stage_id}" for stage_id in STAGE_ORDER if stage_id not in ids]
    for stage in registry.get("stages", []):
        if stage.get("product_pass_claim_allowed") is not False:
            failures.append(f"{stage.get('stage_id')} allows product pass claim")
        if any(item in stage.get("cannot_unlock", []) for item in ["E03", "E04", "D08"]) is False:
            failures.append(f"{stage.get('stage_id')} missing scaleout cannot_unlock")
    return {"schema": "stage_registry_validation.v1", "pass": not failures, "failures": failures, "product_pass": False}
