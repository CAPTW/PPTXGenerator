from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.compiler.pptx_primitive import validate_primitive
from src.presentation_agent.magic_layer.schemas.common import duplicate_ids


def validate_primitive_plan(plan: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    primitives = plan.get("primitives", [])
    for duplicate in duplicate_ids(primitives, "primitive_id"):
        failures.append(f"duplicate primitive_id: {duplicate}")
    for primitive in primitives:
        validation = validate_primitive(primitive)
        failures.extend(validation["failures"])
    if "B03_native_validation_gate" not in plan.get("downstream_gates", []):
        failures.append("B03 downstream gate required")
    return {"schema": "primitive_plan_validation.v1", "pass": not failures, "failures": failures, "primitive_count": len(primitives)}
