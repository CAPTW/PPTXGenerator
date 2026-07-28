"""Schema loading and validation for executable Template Contract V2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_CONTRACT_V2_SCHEMA_PATH = REPO_ROOT / "schemas" / "template_contract_v2.schema.json"
SUPPORTED_CONTRACT_VERSION = "2"


@dataclass(frozen=True, slots=True)
class ContractValidationError(ValueError):
    code: str
    message: str
    errors: tuple[str, ...] = ()

    def __str__(self) -> str:
        return self.message


def load_template_contract(path: str | Path) -> dict[str, Any]:
    contract_path = Path(path)
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_template_contract_payload(payload)
    payload = dict(payload)
    payload["_contract_path"] = _display_path(contract_path)
    return payload


def load_template_contract_schema() -> dict[str, Any]:
    return json.loads(TEMPLATE_CONTRACT_V2_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_template_contract_payload(payload: dict[str, Any]) -> dict[str, Any]:
    schema = load_template_contract_schema()
    validator = Draft202012Validator(schema)
    validator.validate(payload)
    return payload


def required_slot_ids(contract: dict[str, Any]) -> tuple[str, ...]:
    explicit = [str(item) for item in contract.get("required_slots") or [] if str(item).strip()]
    from_contracts = [
        str(slot.get("slot_id"))
        for slot in contract.get("slot_contracts") or []
        if isinstance(slot, dict) and slot.get("required") and str(slot.get("slot_id") or "").strip()
    ]
    return tuple(dict.fromkeys([*explicit, *from_contracts]))


def slot_contracts_by_id(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(slot.get("slot_id")): slot
        for slot in contract.get("slot_contracts") or []
        if isinstance(slot, dict) and str(slot.get("slot_id") or "").strip()
    }


def contract_allowlist(contract: dict[str, Any]) -> list[dict[str, Any]]:
    warning_policy = contract.get("warning_policy")
    if not isinstance(warning_policy, dict):
        return []
    allowlist = warning_policy.get("allowlist")
    return [item for item in allowlist if isinstance(item, dict)] if isinstance(allowlist, list) else []


def is_supported_contract_version(contract: dict[str, Any]) -> bool:
    return str(contract.get("contract_version") or "") == SUPPORTED_CONTRACT_VERSION


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()
