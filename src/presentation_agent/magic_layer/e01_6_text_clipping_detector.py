"""Deterministic text clipping and semantic object collision checks for E01.6."""

from __future__ import annotations

from typing import Any


def estimate_text_fits(text: str, width_in: float, height_in: float, font_pt: float) -> bool:
    estimated_width = len(text) * (font_pt / 72.0) * 0.46
    estimated_height = (font_pt / 72.0) * 1.25
    return estimated_width <= width_in and estimated_height <= height_in


def detect_text_clipping(action_items: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    findings = []
    for item in action_items:
        for kind, text_key, box_key, font_key in [
            ("primary", "primary_label", "primary_label_bbox_in", "top_font_pt"),
            ("secondary", "secondary_label", "secondary_label_bbox_in", "bottom_font_pt"),
        ]:
            box = item[box_key]
            fits = estimate_text_fits(item[text_key], box["w"], box["h"], item[font_key])
            if not fits:
                findings.append({"action_id": item["action_id"], "kind": kind, "text": item[text_key], "bbox_in": box, "font_pt": item[font_key]})
    clipping = {
        "schema_name": "text_clipping_report",
        "status": "passed" if not findings else "patch_required",
        "text_clipping_count": len(findings),
        "findings": findings,
        "canva_parity_claimed": False,
    }
    overflow = {
        "schema_name": "text_overflow_report",
        "status": "passed" if not findings else "patch_required",
        "text_overflow_count": len(findings),
        "findings": findings,
        "canva_parity_claimed": False,
    }
    return clipping, overflow


def detect_object_collisions(action_items: list[dict[str, Any]]) -> dict[str, Any]:
    collisions = []
    for idx, left in enumerate(action_items):
        for right in action_items[idx + 1 :]:
            if _overlaps(left["bbox_in"], right["bbox_in"]):
                collisions.append({"left": left["action_id"], "right": right["action_id"]})
        if _overlaps(left["icon_bbox_in"], left["primary_label_bbox_in"]) or _overlaps(left["icon_bbox_in"], left["secondary_label_bbox_in"]):
            collisions.append({"left": f"{left['action_id']}_icon", "right": f"{left['action_id']}_label"})
    return {
        "schema_name": "object_collision_report",
        "status": "passed" if not collisions else "patch_required",
        "object_collision_count": len(collisions),
        "semantic_group_collision_count": len(collisions),
        "nonsemantic_decorative_overlap_allowed_count": 0,
        "collisions": collisions,
        "canva_parity_claimed": False,
    }


def _overlaps(a: dict[str, float], b: dict[str, float]) -> bool:
    return not (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"] or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])
