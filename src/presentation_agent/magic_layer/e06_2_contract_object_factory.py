"""Object planning helpers for contract-first PPTX compilation."""

from __future__ import annotations

import re
from typing import Any


def build_contract_compile_object_plan(contract: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for slide in contract.get("slides", []):
        for obj in sorted(slide.get("objects", []), key=lambda row: row.get("z_order", 0)):
            object_type = obj.get("object_type", "shape")
            counts[object_type] = counts.get(object_type, 0) + 1
            rows.append(
                {
                    "slide_number": slide.get("slide_number"),
                    "archetype_id": slide.get("archetype_id"),
                    "contract_object_id": obj.get("object_id"),
                    "object_type": object_type,
                    "semantic_role": obj.get("semantic_role"),
                    "z_order": obj.get("z_order"),
                    "bbox_emu": obj.get("bbox_emu"),
                    "factory": factory_for_object(obj),
                }
            )
    return {
        "schema_name": "contract_compile_object_plan",
        "status": "passed" if rows else "failed",
        "slide_count": len(contract.get("slides", [])),
        "object_count": len(rows),
        "object_counts_by_type": counts,
        "objects": rows[:300],
    }


def factory_for_object(obj: dict[str, Any]) -> str:
    object_type = obj.get("object_type")
    if object_type == "semantic_icon":
        return "svg_icon_factory"
    if object_type in {"text", "source_footer"} and str(obj.get("text_excerpt") or "").strip():
        return "text_factory"
    if object_type in {"table_region", "chart_region"}:
        return "chart_table_factory"
    return "shape_factory"


def contract_shape_name(obj: dict[str, Any]) -> str:
    role = _slug(str(obj.get("semantic_role") or obj.get("object_type") or "object"))
    object_type = _slug(str(obj.get("object_type") or "object"))
    return f"contract::{obj['object_id']}::{object_type}::{role}"


def parse_contract_shape_name(name: str) -> dict[str, str] | None:
    if not name.startswith("contract::"):
        return None
    parts = name.split("::")
    if len(parts) < 4:
        return None
    return {
        "contract_object_id": parts[1],
        "contract_object_type": parts[2],
        "contract_semantic_role": parts[3],
    }


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()[:40]
