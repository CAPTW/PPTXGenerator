"""Native PPT reconstruction readiness planner for fused E01X objects."""

from __future__ import annotations

from typing import Any

from .semantic_roles import is_semantic_role


SEMANTIC_RASTER_FORBIDDEN_ROLES = {
    "title_text_region",
    "subtitle_text_region",
    "body_text_region",
    "source_footer_strip",
    "card_panel",
    "checklist_panel",
    "icon_region",
    "chart_region",
    "table_region",
    "matrix_region",
    "process_node",
    "timeline_phase",
    "connector",
    "technical_overlay",
}

RASTER_TARGETS = {"replaceable_image_frame", "bounded_decorative_raster"}


def target_for_role(role: str) -> str:
    if role in {"title_text_region", "subtitle_text_region", "body_text_region"}:
        return "ppt_text_box"
    if role == "source_footer_strip":
        return "ppt_text_box"
    if role in {"card_panel", "checklist_panel", "matrix_region", "process_node", "timeline_phase", "technical_overlay"}:
        return "ppt_shape_group"
    if role == "icon_region":
        return "svg_vector"
    if role == "chart_region":
        return "native_chart"
    if role == "table_region":
        return "native_table"
    if role == "connector":
        return "ppt_connector"
    if role in {"hero_visual_field", "replaceable_image_frame"}:
        return "replaceable_image_frame"
    if role in {"decorative_texture", "accent_line", "shadow_or_glow"}:
        return "bounded_decorative_raster"
    if role == "background_base":
        return "ppt_shape"
    return "reject_unknown"


def build_native_reconstruction_readiness_plan(objects: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    semantic_raster_violations = 0
    unknown_layer_violations = 0
    promotable_count = 0
    semantic_count = 0
    for obj in objects:
        role = obj.get("semantic_role", "unknown")
        target = obj.get("editability_target") or target_for_role(role)
        semantic = bool(obj.get("content_bearing")) or is_semantic_role(role)
        if semantic:
            semantic_count += 1
        semantic_raster_violation = semantic and role in SEMANTIC_RASTER_FORBIDDEN_ROLES and target in RASTER_TARGETS
        unknown_violation = role == "unknown" and bool(obj.get("content_bearing"))
        if semantic_raster_violation:
            semantic_raster_violations += 1
        if unknown_violation or target == "reject_unknown":
            unknown_layer_violations += 1
        possible = not semantic_raster_violation and not unknown_violation and target != "reject_unknown"
        if possible:
            promotable_count += 1
        rows.append(
            {
                "object_id": obj.get("object_id"),
                "semantic_role": role,
                "content_bearing": bool(obj.get("content_bearing")),
                "editability_target": target,
                "native_promotion_possible": possible,
                "native_promotion_blockers": _blockers(semantic_raster_violation, unknown_violation, target),
                "semantic_raster_violation": semantic_raster_violation,
                "unknown_layer_violation": unknown_violation,
                "requires_e01_patch": not possible,
            }
        )
    readiness_rate = promotable_count / len(rows) if rows else 0.0
    return {
        "schema_name": "native_reconstruction_readiness_plan",
        "schema_version": "1.0",
        "objects": rows,
        "summary": {
            "object_count": len(rows),
            "semantic_object_count": semantic_count,
            "native_promotion_possible_count": promotable_count,
            "native_promotion_readiness_rate": readiness_rate,
            "semantic_raster_violation_count": semantic_raster_violations,
            "unknown_layer_violation_count": unknown_layer_violations,
            "semantic_objects_without_native_target": sum(1 for row in rows if row["editability_target"] == "reject_unknown"),
        },
        "canva_parity_claimed": False,
    }


def _blockers(semantic_raster_violation: bool, unknown_violation: bool, target: str) -> list[str]:
    blockers: list[str] = []
    if semantic_raster_violation:
        blockers.append("semantic_raster_violation")
    if unknown_violation:
        blockers.append("unknown_content_bearing_layer")
    if target == "reject_unknown":
        blockers.append("unknown_final_pptx_target")
    return blockers
