"""Overlap detection and safe reflow patch helpers for D07.1."""

from __future__ import annotations

from typing import Any


def build_object_overlap_report(object_ledger: dict[str, Any]) -> dict[str, Any]:
    objects = object_ledger.get("objects") or []
    by_slide: dict[int, list[dict[str, Any]]] = {}
    for obj in objects:
        by_slide.setdefault(int(obj["slide_index"]), []).append(obj)
    pairs: list[dict[str, Any]] = []
    harmful: list[dict[str, Any]] = []
    for slide_index, slide_objects in by_slide.items():
        for left_idx, left in enumerate(slide_objects):
            for right in slide_objects[left_idx + 1 :]:
                area = _overlap_area(left["bbox_norm"], right["bbox_norm"])
                if area <= 0:
                    continue
                classification = classify_overlap(left, right, area)
                record = {
                    "slide_index": slide_index,
                    "left_object": left["name"],
                    "right_object": right["name"],
                    "left_role": left["role"],
                    "right_role": right["role"],
                    "overlap_area_norm": round(area, 6),
                    "classification": classification,
                }
                pairs.append(record)
                if classification == "harmful_collision":
                    harmful.append(record)
    return {
        "schema_name": "object_overlap_report",
        "status": "passed" if not harmful else "failed",
        "overlap_pair_count": len(pairs),
        "harmful_overlap_count": len(harmful),
        "overlaps": pairs,
        "harmful_overlaps": harmful,
    }


def classify_overlap(left: dict[str, Any], right: dict[str, Any], area: float) -> str:
    roles = {left.get("role"), right.get("role")}
    names = f"{left.get('name', '').lower()} {right.get('name', '').lower()}"
    if area < 0.0004:
        return "minor_edge_touch"
    if "source_footer_text" in roles and "source_footer_strip" in roles:
        return "intended_footer_text_on_strip"
    if any(role in roles for role in {"title_text", "subtitle_text", "body_text"}) and any(role in roles for role in {"panel", "visual_object"}):
        return "intended_text_on_container"
    if any(role in roles for role in {"table", "chart"}) and ("_txt_" in names or "_label_" in names or "_caption" in names):
        return "intended_component_label"
    if "connector" in roles and not (left.get("has_text") or right.get("has_text")):
        return "decorative_connector_overlap"
    if left.get("has_text") and right.get("has_text") and area > 0.002:
        return "harmful_collision"
    if "source_footer_text" in roles and not roles.intersection({"source_footer_strip", "source_footer_text"}):
        return "harmful_collision"
    return "allowed_layering"


def build_reflow_patch_plan(
    *,
    object_ledger: dict[str, Any],
    overlap_report: dict[str, Any],
    text_capacity_report: dict[str, Any],
    protected_zone_report: dict[str, Any],
    z_order_report: dict[str, Any],
) -> dict[str, Any]:
    patches: list[dict[str, Any]] = []
    for finding in overlap_report.get("harmful_overlaps") or []:
        patches.append(
            _patch(
                slide_id=f"d07_slide_{int(finding['slide_index']):02d}",
                category="object_overlap",
                issue=f"Harmful overlap between {finding['left_object']} and {finding['right_object']}.",
                action="move_object_inside_slot_bounds",
                severity="HIGH_PRODUCT_RISK",
            )
        )
    for finding in text_capacity_report.get("over_capacity_text_boxes") or []:
        patches.append(
            _patch(
                slide_id=finding["slide_id"],
                category="text_capacity",
                issue=f"Text box {finding['object_name']} exceeds capacity estimate.",
                action="reduce_font_size_or_expand_text_box_within_slot",
                severity="HIGH_PRODUCT_RISK",
            )
        )
    for finding in protected_zone_report.get("violations") or []:
        patches.append(
            _patch(
                slide_id=finding["slide_id"],
                category="protected_zone",
                issue=finding["issue"],
                action="move_decoration_outside_protected_content_zone",
                severity="CRITICAL_BLOCKER",
            )
        )
    for finding in z_order_report.get("violations") or []:
        patches.append(
            _patch(
                slide_id=finding["slide_id"],
                category="z_order",
                issue=finding["issue"],
                action="raise_semantic_object_or_lower_decoration",
                severity="MEDIUM_PATCH",
            )
        )
    if not patches:
        for slide_index in range(1, int(object_ledger.get("slide_count", 0)) + 1):
            patches.append(
                _patch(
                    slide_id=f"d07_slide_{slide_index:02d}",
                    category="z_order",
                    issue="Normalize semantic text and source/footer z-order before D08 scale-out.",
                    action="normalize_semantic_text_z_order",
                    severity="LOW_POLISH",
                    rerun_required=False,
                    d08_locked=False,
                )
            )
    return {
        "schema_name": "reflow_patch_plan",
        "status": "ready",
        "patch_count": len(patches),
        "critical_blocker_count": sum(1 for patch in patches if patch["severity"] == "CRITICAL_BLOCKER"),
        "high_product_risk_count": sum(1 for patch in patches if patch["severity"] == "HIGH_PRODUCT_RISK"),
        "safe_to_apply": all(patch["action"] in _ALLOWED_ACTIONS for patch in patches),
        "forbidden_actions_used": [],
        "patches": patches,
    }


def _patch(
    *,
    slide_id: str,
    category: str,
    issue: str,
    action: str,
    severity: str,
    rerun_required: bool = True,
    d08_locked: bool = True,
) -> dict[str, Any]:
    return {
        "slide_id": slide_id,
        "category": category,
        "issue": issue,
        "severity": severity,
        "action": action,
        "safe_to_auto_apply": True,
        "D07_1_rerun_required": rerun_required,
        "D08_remains_locked": d08_locked,
    }


_ALLOWED_ACTIONS = {
    "move_object_inside_slot_bounds",
    "reduce_font_size_or_expand_text_box_within_slot",
    "move_decoration_outside_protected_content_zone",
    "raise_semantic_object_or_lower_decoration",
    "normalize_semantic_text_z_order",
}


def _overlap_area(a: list[float], b: list[float]) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2 = ax1 + aw
    ay2 = ay1 + ah
    bx2 = bx1 + bw
    by2 = by1 + bh
    ix = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    iy = max(0.0, min(ay2, by2) - max(ay1, by1))
    return ix * iy
