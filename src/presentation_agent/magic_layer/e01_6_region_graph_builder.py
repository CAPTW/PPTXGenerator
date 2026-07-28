"""Region graph v2 for the E01.6 single-slide Magic Layer+ polish gate."""

from __future__ import annotations

from typing import Any


REGION_BBOX_IN = {
    "background_base": {"x": 0.0, "y": 0.0, "w": 16.0, "h": 9.0},
    "hero_visual_field": {"x": 0.0, "y": 0.0, "w": 9.72, "h": 7.02},
    "hero_technical_overlay": {"x": 0.2, "y": 0.3, "w": 8.9, "h": 6.2},
    "thumbnail_callout_group": {"x": 3.45, "y": 5.45, "w": 5.9, "h": 1.65},
    "checklist_panel_outer_frame": {"x": 9.66, "y": 0.31, "w": 6.08, "h": 7.08},
    "checklist_title_region": {"x": 10.52, "y": 0.56, "w": 4.35, "h": 0.42},
    "checklist_step_group_01": {"x": 9.84, "y": 1.13, "w": 5.72, "h": 1.12},
    "checklist_step_group_02": {"x": 9.84, "y": 2.36, "w": 5.72, "h": 1.12},
    "checklist_step_group_03": {"x": 9.84, "y": 3.6, "w": 5.72, "h": 1.12},
    "checklist_step_group_04": {"x": 9.84, "y": 4.84, "w": 5.72, "h": 1.12},
    "checklist_step_group_05": {"x": 9.84, "y": 6.07, "w": 5.72, "h": 1.12},
    "checklist_chevron_group": {"x": 15.18, "y": 1.35, "w": 0.33, "h": 5.5},
    "bottom_action_bar": {"x": 0.0, "y": 7.48, "w": 16.0, "h": 1.26},
    "bottom_action_item_ppe": {"x": 0.42, "y": 7.68, "w": 2.92, "h": 0.72},
    "bottom_action_item_zero_leak": {"x": 3.48, "y": 7.68, "w": 2.92, "h": 0.72},
    "bottom_action_item_chemical_barrier": {"x": 6.54, "y": 7.68, "w": 2.92, "h": 0.72},
    "bottom_action_item_communicate": {"x": 9.6, "y": 7.68, "w": 2.92, "h": 0.72},
    "bottom_action_item_teamwork": {"x": 12.66, "y": 7.68, "w": 2.92, "h": 0.72},
    "source_footer_strip": {"x": 0.42, "y": 8.78, "w": 14.85, "h": 0.18},
    "decorative_accent_marks": {"x": 0.0, "y": 7.48, "w": 16.0, "h": 1.26},
}


def build_region_graph_v2() -> dict[str, Any]:
    regions = []
    for index, (region_id, bbox) in enumerate(REGION_BBOX_IN.items(), start=1):
        patch_required = region_id == "bottom_action_bar" or region_id.startswith("bottom_action_item")
        regions.append(
            {
                "region_id": region_id,
                "bbox_in": bbox,
                "child_objects": _children(region_id),
                "object_types": _object_types(region_id),
                "semantic_role": region_id,
                "content_bearing": _content_bearing(region_id),
                "editability_target": _editability_target(region_id),
                "z_order_range": [index * 10, index * 10 + 9],
                "expected_visual_role": _expected_visual_role(region_id),
                "current_failure_status": "PATCH_REQUIRED" if patch_required else "PASS_OR_AUDIT_ONLY",
                "patch_action": "rebuild_as_atomic_semantic_group" if patch_required else "audit_preserve",
            }
        )
    return {
        "schema_name": "region_graph_v2",
        "status": "passed",
        "region_count": len(regions),
        "required_regions_present": sorted(REGION_BBOX_IN),
        "regions": regions,
        "canva_parity_claimed": False,
    }


def _children(region_id: str) -> list[str]:
    if region_id.startswith("bottom_action_item"):
        return [f"{region_id}_icon", f"{region_id}_primary_label", f"{region_id}_secondary_label", f"{region_id}_divider"]
    if region_id.startswith("checklist_step"):
        return [f"{region_id}_icon", f"{region_id}_number", f"{region_id}_heading", f"{region_id}_body", f"{region_id}_chevron"]
    if region_id == "bottom_action_bar":
        return [key for key in REGION_BBOX_IN if key.startswith("bottom_action_item")]
    return []


def _object_types(region_id: str) -> list[str]:
    if "visual" in region_id or "thumbnail" in region_id:
        return ["bounded_picture", "native_shape", "editable_text"]
    if region_id.startswith("bottom_action") or region_id.startswith("checklist"):
        return ["native_shape", "ppt_text", "native_vector_icon"]
    if "footer" in region_id:
        return ["ppt_text", "native_line"]
    return ["native_shape"]


def _content_bearing(region_id: str) -> bool:
    return any(token in region_id for token in ["action_item", "checklist", "footer", "thumbnail", "hero_visual"])


def _editability_target(region_id: str) -> str:
    if region_id.startswith("bottom_action") or region_id.startswith("checklist") or "footer" in region_id:
        return "ppt_native_shapes_text_and_vector_icons"
    if "visual" in region_id or "thumbnail" in region_id:
        return "bounded_replaceable_visual_field"
    return "ppt_native_shape"


def _expected_visual_role(region_id: str) -> str:
    if region_id == "bottom_action_bar":
        return "stable five-item safety/action semantic bar with readable labels"
    if region_id.startswith("bottom_action_item"):
        return "atomic icon plus two-line editable label group"
    return region_id.replace("_", " ")
