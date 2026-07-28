from __future__ import annotations

from typing import Any


def validate_gate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if not contract.get("missing_b03_blocks"):
        failures.append("missing B03 gate must block")
    if not contract.get("missing_b01_blocks"):
        failures.append("missing B01 gate must block")
    if contract.get("pass_with_limitations_is_product_pass"):
        failures.append("PASS_WITH_LIMITATIONS cannot be product PASS")
    if not contract.get("scaleout_lock_must_remain_closed"):
        failures.append("scaleout lock must remain closed")
    return {"schema": "gate_contract_validation.v1", "pass": not failures, "failures": failures, "product_pass": False}
