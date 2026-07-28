from __future__ import annotations

from typing import Any

from ..pipeline_dag import validate_pipeline_dag


def validate_dag(dag: dict[str, Any], registry: dict[str, Any] | None = None) -> dict[str, Any]:
    return validate_pipeline_dag(dag, registry)
