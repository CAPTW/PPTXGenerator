from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.compiler.backend_capability import supports_instruction_type


ALTERNATIVES = {
    "native_chart": "editable_shape_chart",
    "native_table": "editable_shape_grid_table",
}


def evaluate_unsupported_instruction(instruction: dict[str, Any], capability: dict[str, Any]) -> dict[str, Any]:
    instruction_type = str(instruction.get("pptx_object_type", ""))
    required = bool(instruction.get("editable_required", instruction.get("required", True)))
    if supports_instruction_type(instruction_type, capability):
        return {
            "instruction_id": instruction.get("instruction_id"),
            "reason": "",
            "required": required,
            "alternative_mapping_available": False,
            "alternative_mapping": None,
            "blocks_compile": False,
            "warning_or_fatal": "none",
            "evidence": "backend supports instruction",
        }
    alternative = ALTERNATIVES.get(instruction_type)
    alternative_available = bool(alternative and supports_instruction_type(alternative, capability))
    blocks = required and not alternative_available
    return {
        "instruction_id": instruction.get("instruction_id"),
        "reason": f"backend does not support {instruction_type}",
        "required": required,
        "alternative_mapping_available": alternative_available,
        "alternative_mapping": alternative if alternative_available else None,
        "blocks_compile": blocks,
        "warning_or_fatal": "fatal" if blocks else "warning",
        "evidence": capability.get("backend_name", "unknown"),
    }
