from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.presentation_agent.magic_layer.planning.geometry_resolver import bbox_norm_to_slide, object_bbox
from src.presentation_agent.magic_layer.schemas.common import is_semantic_object


def normalize_instruction(instruction: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(instruction)
    warnings: list[str] = []
    blockers: list[str] = []
    ident = data.get("instruction_id", data.get("object_id", "instruction"))
    required = bool(data.get("editable_required", True))
    if required and not data.get("object_name"):
        blockers.append(f"{ident}: missing required object name")
    elif not data.get("object_name"):
        warnings.append(f"{ident}: optional object name missing")
    geometry = data.get("geometry", {})
    bbox = object_bbox(data)
    slide_geometry = bbox_norm_to_slide(bbox)
    if not slide_geometry.get("pass"):
        blockers.append(f"{ident}: invalid bbox")
    else:
        data["geometry"] = {**geometry, **slide_geometry}
    data["z_order"] = int(data.get("z_order", 0) or 0)
    data.setdefault("validation_checks", [])
    data.setdefault("review_hook_ids", [])
    data.setdefault("patch_hook_ids", [])
    if data.get("raster_allowed") is True and is_semantic_object(data):
        blockers.append(f"{ident}: semantic raster flag cannot be normalized away")
    if data.get("evidence_path", "").lower().find("quarantine") >= 0:
        blockers.append(f"{ident}: quarantined evidence forbidden")
    if data.get("evidence_path", "").lower().find("manual") >= 0:
        blockers.append(f"{ident}: manual-review evidence forbidden")
    return {"schema": "instruction_normalization.v1", "pass": not blockers, "instruction": data, "warnings": warnings, "blockers": blockers}
