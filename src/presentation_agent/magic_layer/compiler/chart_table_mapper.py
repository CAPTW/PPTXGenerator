from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.compiler.backend_capability import supports_instruction_type
from src.presentation_agent.magic_layer.compiler.pptx_primitive import map_instruction_to_primitive, validate_primitive


ALLOWED = {"native_chart", "editable_shape_chart", "native_table", "editable_shape_grid_table"}


def map_chart_or_table(instruction: dict[str, Any], capability: dict[str, Any]) -> dict[str, Any]:
    instruction_type = str(instruction.get("pptx_object_type", ""))
    failures: list[str] = []
    if instruction_type not in ALLOWED:
        failures.append("raster chart/table fallback forbidden")
    elif not supports_instruction_type(instruction_type, capability):
        failures.append(f"backend does not support {instruction_type}")
    primitive = map_instruction_to_primitive(instruction, capability.get("backend_name", "dry_run_only"))
    validation = validate_primitive(primitive)
    failures.extend(validation["failures"])
    return {"schema": "chart_table_mapping_result.v1", "pass": not failures, "primitive": primitive, "failures": failures}
