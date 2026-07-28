from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.template.archetype_taxonomy import validate_archetype_contract


def validate_contract_against_archetype(contract: dict[str, Any]) -> dict[str, Any]:
    return validate_archetype_contract(str(contract.get("archetype_id", "")), contract)
