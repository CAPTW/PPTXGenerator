from __future__ import annotations

from typing import Any

from .pipeline_state import build_pipeline_state


def build_pipeline_context(mode: str = "IMPORT_EXISTING") -> dict[str, Any]:
    return {
        "schema": "pipeline_context.v1",
        "state": build_pipeline_state(mode=mode),
        "quarantine_excluded": True,
        "protected_artifacts_writable": False,
        "product_pass": False,
    }
