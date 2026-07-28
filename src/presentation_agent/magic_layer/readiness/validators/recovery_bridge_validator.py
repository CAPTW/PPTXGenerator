from __future__ import annotations

from typing import Any


def validate_recovery_bridge_decision(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "recovery_bridge_validator.v1",
        "pass": decision.get("rv00_objective_lock_allowed") is True and decision.get("e03_direct_rerun_allowed") is False,
        "decision": decision.get("decision"),
        "product_pass": False,
    }
