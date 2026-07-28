from __future__ import annotations

"""Adapter boundary around the current non-PPTX runtime contracts and state IO."""

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ..non_pptx_modules import contracts as _legacy_contracts
from ..non_pptx_modules import state_schemas as _legacy_state_schemas


WorkflowGate = _legacy_contracts.WorkflowGate
SKILL_NAMES = _legacy_contracts.SKILL_NAMES
STATE_SCHEMA_NAMES = _legacy_contracts.STATE_SCHEMA_NAMES
COMPAT_STATE_SCHEMA_NAMES = _legacy_contracts.COMPAT_STATE_SCHEMA_NAMES
SchemaModel = _legacy_state_schemas.SchemaModel


@runtime_checkable
class LegacyStateIO(Protocol):
    """Capability surface for legacy state file loading and saving."""

    def load(self, path: str | Path) -> SchemaModel:
        ...

    def save(self, model: SchemaModel, path: str | Path) -> Path:
        ...


class DefaultLegacyStateIO:
    """Default backend that preserves the current legacy state file behavior."""

    def load(self, path: str | Path) -> SchemaModel:
        return _legacy_state_schemas.load_state_file(path)

    def save(self, model: SchemaModel, path: str | Path) -> Path:
        return _legacy_state_schemas.save_state_file(model, path)


DEFAULT_LEGACY_STATE_IO: LegacyStateIO = DefaultLegacyStateIO()


def load_state_file(path: str | Path) -> SchemaModel:
    return DEFAULT_LEGACY_STATE_IO.load(path)


def save_state_file(model: SchemaModel, path: str | Path) -> Path:
    return DEFAULT_LEGACY_STATE_IO.save(model, path)


def __getattr__(name: str) -> Any:
    if hasattr(_legacy_state_schemas, name):
        return getattr(_legacy_state_schemas, name)
    if hasattr(_legacy_contracts, name):
        return getattr(_legacy_contracts, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    names = {
        *globals().keys(),
        *vars(_legacy_contracts).keys(),
        *vars(_legacy_state_schemas).keys(),
    }
    return sorted(name for name in names if not name.startswith("_"))
