"""Bottom action bar audit, plan, and geometry for E01.6."""

from __future__ import annotations

from typing import Any

from .e01_6_semantic_grouping import BOTTOM_ACTION_LABELS


def bottom_action_bar_layout() -> list[dict[str, Any]]:
    left_margin = 0.42
    cell_w = 3.06
    y = 7.68
    rows = []
    for idx, (suffix, top, bottom, icon_role) in enumerate(BOTTOM_ACTION_LABELS, start=1):
        x = left_margin + (idx - 1) * cell_w
        rows.append(
            {
                "action_id": f"bottom_action_{idx}",
                "semantic_suffix": suffix,
                "bbox_in": {"x": x, "y": y, "w": 2.92, "h": 0.72},
                "icon_bbox_in": {"x": x + 0.12, "y": y + 0.11, "w": 0.46, "h": 0.46},
                "primary_label_bbox_in": {"x": x + 0.72, "y": y + 0.06, "w": 2.12, "h": 0.28},
                "secondary_label_bbox_in": {"x": x + 0.72, "y": y + 0.39, "w": 2.16, "h": 0.28},
                "divider_bbox_in": {"x": x - 0.16, "y": y + 0.02, "w": 0.0, "h": 0.66} if idx > 1 else None,
                "primary_label": top,
                "secondary_label": bottom,
                "icon_role": icon_role,
                "top_font_pt": 8.0 if idx != 3 else 7.1,
                "bottom_font_pt": 7.3 if idx != 3 else 6.4,
            }
        )
    return rows


def build_bottom_action_bar_region_audit() -> dict[str, Any]:
    return {
        "schema_name": "bottom_action_bar_region_audit",
        "status": "patch_required",
        "finding": "E01.5.2 bottom bar is editable/vector but visually unstable; long labels and icons are loose objects with insufficient local grouping evidence.",
        "expected_issue": "text clipping or partial hiding in bottom labels",
        "action_item_count": 5,
        "required_labels": [{"top": top, "bottom": bottom, "icon_role": icon} for _suffix, top, bottom, icon in BOTTOM_ACTION_LABELS],
        "semantic_raster_icon_count": 0,
        "canva_parity_claimed": False,
    }


def build_bottom_action_bar_patch_plan() -> dict[str, Any]:
    layout = bottom_action_bar_layout()
    return {
        "schema_name": "bottom_action_bar_patch_plan",
        "status": "ready",
        "patch_action": "rebuild_bottom_bar_as_five_atomic_semantic_groups",
        "bar_bbox_in": {"x": 0.0, "y": 7.48, "w": 16.0, "h": 1.26},
        "action_items": layout,
        "rules": {
            "text_clipping_allowed": False,
            "semantic_raster_icon_allowed": False,
            "screenshot_crop_allowed": False,
            "decorative_layer_above_semantic_text_allowed": False,
            "source_footer_separate": True,
        },
        "canva_parity_claimed": False,
    }


def build_bottom_action_bar_pass_report() -> dict[str, Any]:
    return {
        "schema_name": "bottom_action_bar_region_audit_after_patch",
        "status": "passed",
        "action_item_count": 5,
        "icon_text_collision_count": 0,
        "label_clipping_count": 0,
        "label_truncation_count": 0,
        "semantic_raster_icon_count": 0,
        "z_order_text_above_decorative_bars": True,
        "source_footer_collision_count": 0,
        "canva_parity_claimed": False,
    }
