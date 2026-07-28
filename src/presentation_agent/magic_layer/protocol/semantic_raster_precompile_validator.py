from __future__ import annotations

from typing import Any

from ..schemas.common import is_full_slide_bbox, is_raster_target, is_semantic_object, is_semantic_text, is_structured_semantic


def validate_semantic_raster_precompile(
    psd_like_layer_model: dict[str, Any] | None = None,
    object_graph: dict[str, Any] | None = None,
    layer_manifest: dict[str, Any] | None = None,
    semantic_slot_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    semantic_violations = 0
    full_slide = 0
    nonsemantic_raster = 0
    explicit_reject = 0

    candidates: list[dict[str, Any]] = []
    for source in (psd_like_layer_model or {}).get("layers", []) or []:
        candidates.append(source)
    for source in (object_graph or {}).get("objects", []) or []:
        candidates.append(source)
    for source in (layer_manifest or {}).get("layers", []) or []:
        candidates.append(source)
    for slot in (semantic_slot_graph or {}).get("slots", []) or []:
        candidates.append(
            {
                "id": slot.get("slot_id"),
                "semantic_role": slot.get("semantic_role"),
                "kind": slot.get("slot_type"),
                "pptx_target": slot.get("native_target"),
                "content_bearing": slot.get("required"),
                "bbox_norm": slot.get("bbox_norm"),
            }
        )

    for item in candidates:
        item_id = item.get("id") or item.get("object_id") or item.get("layer_id") or "<unknown>"
        target = str(item.get("pptx_target") or item.get("native_target") or "")
        if target == "explicit_reject":
            explicit_reject += 1
            continue
        if is_full_slide_bbox(item.get("bbox_norm")) and (is_raster_target(target) or item.get("raster_allowed")):
            full_slide += 1
            failures.append(f"Full-slide raster plan {item_id} is fatal before compile.")
            continue
        semantic = is_semantic_object(item)
        if semantic and is_raster_target(target):
            semantic_violations += 1
            failures.append(f"Semantic object {item_id} cannot target raster fallback {target}.")
        elif semantic and target == "replaceable_image_frame" and (is_semantic_text(item) or is_structured_semantic(item)):
            semantic_violations += 1
            failures.append(f"Semantic text/structured object {item_id} cannot remain in replaceable image frame.")
        elif not semantic and (item.get("raster_allowed") or target == "replaceable_image_frame"):
            nonsemantic_raster += 1

    return {
        "schema_name": "semantic_raster_precompile_validation",
        "semantic_raster_violation_count": semantic_violations,
        "full_slide_raster_plan_count": full_slide,
        "raster_allowed_nonsemantic_count": nonsemantic_raster,
        "explicit_reject_count": explicit_reject,
        "pass": not failures,
        "failures": failures,
    }
