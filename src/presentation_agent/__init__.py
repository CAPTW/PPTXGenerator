from __future__ import annotations

"""Harness-first public package surface for presentation_agent."""

import importlib
import sys


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

for _module_name in _COMPAT_SUBMODULES:
    _module = importlib.import_module(f"{__name__}.legacy_non_pptx_modules.{_module_name}")
    sys.modules.setdefault(f"{__name__}.{_module_name}", _module)


def __getattr__(name: str):
    target = _REMOVED_ROOT_EXPORTS.get(name)
    if target is not None:
        raise AttributeError(
            f"`presentation_agent.{name}` is no longer exported from the package root. "
            f"Use `{target}` for the explicit compatibility path."
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []
