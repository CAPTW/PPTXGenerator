from __future__ import annotations

from typing import Any


def validate_reopen_policy(policy: dict[str, Any]) -> dict[str, Any]:
    ok = policy.get("e03_opened_by_rv00") is False and policy.get("direct_e03_rerun_allowed") is False
    return {"schema": "reopen_policy_validator.v1", "pass": ok, "product_pass": False}

