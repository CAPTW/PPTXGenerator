from __future__ import annotations

"""State-file IO capability boundary for the active presentation path."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from ..non_pptx_modules import state_schemas as _state_schemas


SchemaModel = _state_schemas.SchemaModel
DEFAULT_STATE_FILENAMES = _state_schemas.DEFAULT_STATE_FILENAMES


@runtime_checkable
class StateSchemaIO(Protocol):
    """Capability surface for loading and saving schema-backed state artifacts."""

    def load(self, path: str | Path) -> SchemaModel:
        ...

    def save(self, model: SchemaModel, path: str | Path) -> Path:
        ...


class DefaultStateSchemaIO:
    """Default backend that preserves the current state schema load/save behavior."""

    def load(self, path: str | Path) -> SchemaModel:
        return _state_schemas.load_state_file(path)

    def save(self, model: SchemaModel, path: str | Path) -> Path:
        return _state_schemas.save_state_file(model, path)


DEFAULT_STATE_SCHEMA_IO: StateSchemaIO = DefaultStateSchemaIO()


def load_state_file(path: str | Path) -> SchemaModel:
    return DEFAULT_STATE_SCHEMA_IO.load(path)


def save_state_file(model: SchemaModel, path: str | Path) -> Path:
    return DEFAULT_STATE_SCHEMA_IO.save(model, path)


__all__ = [
    "DEFAULT_STATE_FILENAMES",
    "DEFAULT_STATE_SCHEMA_IO",
    "DefaultStateSchemaIO",
    "SchemaModel",
    "StateSchemaIO",
    "load_state_file",
    "save_state_file",
]
