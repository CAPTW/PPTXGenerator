from __future__ import annotations

from typing import Any


def validate_reference_contract(contract: dict[str, Any]) -> dict[str, Any]:
    modes = contract.get("future_modes", {})
    ok = (
        modes.get("E03_MINIMUM_12_ARCHETYPE_MODE", {}).get("valid_expansion_required") == 8
        and modes.get("E03_FULL_16_ARCHETYPE_MODE", {}).get("valid_expansion_required") == 12
        and contract.get("rv01_e03a_validation_required") is True
    )
    return {"schema": "reference_contract_validator.v1", "pass": ok, "product_pass": False}

