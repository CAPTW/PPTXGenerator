from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.planning.geometry_resolver import object_bbox
from src.presentation_agent.magic_layer.schemas.common import is_full_slide_bbox, is_semantic_object


PROTECTED_OUTPUTS = {
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
}


def detect_compile_blockers(compile_input: dict[str, Any]) -> dict[str, Any]:
    objects = compile_input.get("objects", compile_input.get("editable_candidate_spec", {}).get("objects", []))
    expected_outputs = [str(item).replace("\\", "/") for item in compile_input.get("expected_outputs", [])]
    downstream_gates = compile_input.get("downstream_gates", [])
    blockers: list[dict[str, Any]] = []
    semantic_raster = 0
    full_slide = 0
    unknown = 0
    protected = 0
    if "B03_native_validation_gate" not in downstream_gates:
        blockers.append({"blocker_type": "missing_downstream_b03_obligation", "message": "B03 downstream gate is required"})
    for output in expected_outputs:
        if output in PROTECTED_OUTPUTS or "canonical" in output.lower():
            protected += 1
            blockers.append({"blocker_type": "protected_output", "message": output})
        if "source_bound" in output.lower():
            blockers.append({"blocker_type": "source_bound_output", "message": output})
    for obj in objects:
        ident = obj.get("instruction_id", obj.get("object_id", "instruction"))
        object_type = str(obj.get("pptx_object_type", ""))
        if object_type in {"full_slide_raster", "screenshot_slide"}:
            if object_type == "full_slide_raster":
                full_slide += 1
            blockers.append({"blocker_type": object_type, "instruction_id": ident})
        if object_type == "replaceable_image_frame" and is_full_slide_bbox(object_bbox(obj)):
            full_slide += 1
            blockers.append({"blocker_type": "full_slide_raster", "instruction_id": ident})
        if obj.get("raster_allowed") is True and is_semantic_object(obj):
            semantic_raster += 1
            blockers.append({"blocker_type": "semantic_raster", "instruction_id": ident})
        if str(obj.get("semantic_role", "")).lower().find("unknown") >= 0 and obj.get("editable_required", obj.get("content_bearing", False)):
            unknown += 1
            blockers.append({"blocker_type": "unknown_content_bearing", "instruction_id": ident})
    return {
        "schema": "compile_blocker_report.v1",
        "blockers": blockers,
        "blocker_count": len(blockers),
        "semantic_raster_blocker_count": semantic_raster,
        "full_slide_raster_blocker_count": full_slide,
        "unknown_content_bearing_blocker_count": unknown,
        "protected_output_blocker_count": protected,
        "pass": not blockers,
    }
