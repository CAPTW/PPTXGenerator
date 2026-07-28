from __future__ import annotations

from typing import Any
from copy import deepcopy


def validate_object_name(instruction: dict[str, Any]) -> dict[str, Any]:
    name = str(instruction.get("object_name", ""))
    required = bool(instruction.get("editable_required", True))
    failures: list[str] = []
    warnings: list[str] = []
    if required and not name:
        failures.append("required slot-backed object must have stable object_name")
    if name.lower().startswith(("shape ", "object ", "rand_", "tmp_")):
        (failures if required else warnings).append("random-looking object_name is invalid for required objects")
    return {"pass": not failures, "failures": failures, "warnings": warnings}


def harden_native_component_objects(objects: list[dict[str, Any]], archetype: str) -> dict[str, Any]:
    """Normalize C05 dashboard/table object names without changing semantics."""
    hardened = [deepcopy(item) for item in objects]
    renamed_count = 0
    kpi_value_index = 1
    for item in hardened:
        object_type = str(item.get("pptx_object_type") or "")
        role = str(item.get("semantic_role") or "").lower()
        original_name = str(item.get("object_name") or item.get("slot_id") or item.get("object_id") or "")
        new_name = original_name
        if archetype == "data_dashboard":
            if object_type == "editable_shape_chart" or "chart" in role:
                if original_name.startswith("SLOT_CHART_MAIN") and object_type == "editable_shape_chart":
                    new_name = "SLOT_CHART_MAIN__EDITABLE_SHAPE_CHART_GROUP"
            elif original_name == "SLOT_KPI_VALUE_01" and "kpi" in role:
                new_name = f"SLOT_KPI_VALUE_{kpi_value_index:02d}"
                kpi_value_index += 1
        elif archetype == "table_heavy":
            if object_type == "editable_shape_grid_table" or original_name == "SLOT_TABLE_MAIN":
                if object_type == "editable_shape_grid_table":
                    new_name = "SLOT_TABLE_MAIN__EDITABLE_SHAPE_GRID_TABLE_GROUP"
        if new_name != original_name:
            item["object_name"] = new_name
            renamed_count += 1
        if item.get("editable_required", True) and object_type == "text_box":
            item.setdefault("overflow_policy_id", f"ov_{str(item.get('object_name') or item.get('object_id') or 'text').lower()}")
    validations = [validate_object_name(item) for item in hardened]
    failures = [failure for result in validations for failure in result.get("failures", [])]
    return {
        "schema": "native_component_object_name_hardening.v1",
        "archetype": archetype,
        "objects": hardened,
        "renamed_count": renamed_count,
        "stable_object_name_coverage": "PASS" if not failures else "FAIL",
        "failures": failures,
        "product_pass": False,
    }
