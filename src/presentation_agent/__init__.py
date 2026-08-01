from __future__ import annotations

"""Harness-first public package surface for presentation_agent."""

import importlib
import sys
from types import ModuleType


_COMPAT_SUBMODULES = {
    "approved_apply",
    "asset_derivation",
    "deck_qa",
    "document_asset_crop",
    "gate2_context",
    "gate2_planner",
    "large_deck_orchestration",
    "post_apply_closure",
    "reference_scanner",
    "remediation_execution",
    "reviewed_surrogate_policy",
    "runtime_config",
    "ship_readiness",
    "state_cli",
    "state_schemas",
    "structured_visuals",
    "upstream_fix_authoring",
    "workflow_planner",
}

_REMOVED_ROOT_EXPORTS = {
    "bootstrap_runtime_config": "presentation_agent.compat.runtime_pipeline.bootstrap_runtime_config",
    "resolve_runtime_workspace": "presentation_agent.compat.runtime_pipeline.resolve_runtime_workspace",
    "run_pipeline": "presentation_agent.compat.runtime_pipeline.run_pipeline",
    "run_stage": "presentation_agent.compat.runtime_pipeline.run_stage",
    "validate_runtime_state": "presentation_agent.compat.runtime_pipeline.validate_runtime_state",
}


class _LazyCompatModule(ModuleType):
    """Import a historical root alias only when a caller actually uses it."""

    def __init__(self, public_name: str, target_name: str) -> None:
        super().__init__(public_name)
        self.__dict__["_target_name"] = target_name
        self.__dict__["__package__"] = public_name.rpartition(".")[0]
        self.__dict__["__doc__"] = (
            f"Lazy compatibility alias for {target_name}; use the explicit "
            "presentation_agent.legacy_non_pptx_modules namespace for new code."
        )

    def _load(self) -> ModuleType:
        public_name = self.__name__
        target_name = self.__dict__["_target_name"]
        loaded = importlib.import_module(target_name)
        sys.modules[public_name] = loaded
        setattr(sys.modules[__name__], public_name.rpartition(".")[2], loaded)
        return loaded

    def __getattr__(self, name: str):
        return getattr(self._load(), name)

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(dir(self._load())))


for _module_name in _COMPAT_SUBMODULES:
    _public_name = f"{__name__}.{_module_name}"
    _target_name = f"{__name__}.legacy_non_pptx_modules.{_module_name}"
    sys.modules.setdefault(
        _public_name,
        _LazyCompatModule(_public_name, _target_name),
    )


def __getattr__(name: str):
    if name in _COMPAT_SUBMODULES:
        module = importlib.import_module(f"{__name__}.{name}")
        if isinstance(module, _LazyCompatModule):
            module = module._load()
        return module
    target = _REMOVED_ROOT_EXPORTS.get(name)
    if target is not None:
        raise AttributeError(
            f"`presentation_agent.{name}` is no longer exported from the package root. "
            f"Use `{target}` for the explicit compatibility path."
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []
