from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
EXTERNAL_EXECUTION = (
    SRC / "presentation_agent" / "deckcompiler" / "external_execution"
)
DECKCOMPILER = SRC / "presentation_agent" / "deckcompiler"


def load_external_execution_module(module_name: str) -> ModuleType:
    path = EXTERNAL_EXECUTION / f"{module_name}.py"
    if not path.is_file():
        raise AssertionError(f"missing Phase 4 external execution module: {path}")

    packages = {
        "presentation_agent": SRC / "presentation_agent",
        "presentation_agent.deckcompiler": SRC / "presentation_agent" / "deckcompiler",
        "presentation_agent.deckcompiler.external_execution": EXTERNAL_EXECUTION,
    }
    for package_name, package_path in packages.items():
        if package_name not in sys.modules:
            package = types.ModuleType(package_name)
            package.__path__ = [str(package_path)]  # type: ignore[attr-defined]
            package.__package__ = package_name
            sys.modules[package_name] = package

    full_name = f"presentation_agent.deckcompiler.external_execution.{module_name}"
    existing = sys.modules.get(full_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load Phase 4 module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def load_deckcompiler_module(module_name: str) -> ModuleType:
    path = DECKCOMPILER / f"{module_name}.py"
    if not path.is_file():
        raise AssertionError(f"missing DeckCompiler module: {path}")
    packages = {
        "presentation_agent": SRC / "presentation_agent",
        "presentation_agent.deckcompiler": DECKCOMPILER,
    }
    for package_name, package_path in packages.items():
        if package_name not in sys.modules:
            package = types.ModuleType(package_name)
            package.__path__ = [str(package_path)]  # type: ignore[attr-defined]
            package.__package__ = package_name
            sys.modules[package_name] = package
    full_name = f"presentation_agent.deckcompiler.{module_name}"
    existing = sys.modules.get(full_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load DeckCompiler module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def request_payload(executable_id: str = "openai") -> dict[str, object]:
    return {
        "run_id": "run_0123456789abcdef0123",
        "slide_id": "slide-001",
        "execution_id": "exec_0123456789abcdef0123",
        "attempt_number": 1,
        "external_executable_id": executable_id,
        "prompt_id": "prompt-001",
        "prompt": "Create a restrained 16:9 systems diagram reference.",
        "composition_plan_id": "composition-001",
        "composition_plan_sha256": "1" * 64,
        "requested_model": "gpt-image-2",
        "requested_width": 1920,
        "requested_height": 1080,
        "requested_media_type": "image/png",
        "references": [
            {
                "artifact_id": "art_0123456789abcdef0123",
                "sha256": "2" * 64,
            }
        ],
        "source_commit": "8c9f7f1d6ef15868010e2aa9e5bf52467b8e468d",
        "upstream_artifact_ids": ["art_0123456789abcdef0123"],
    }
