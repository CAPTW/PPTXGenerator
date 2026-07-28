"""Detect repeated semantic slots that collapse to the same geometry."""

from __future__ import annotations

from typing import Any


def detect_duplicate_bbox_collisions(records: list[dict[str, Any]], *, iou_threshold: float = 0.85) -> dict[str, Any]:
    normalized = [_normalize_record(record) for record in records if record.get("bbox_norm") is not None]
    collisions: list[dict[str, Any]] = []
    for left_index, left in enumerate(normalized):
        for right in normalized[left_index + 1 :]:
            iou = bbox_iou(left["bbox_norm"], right["bbox_norm"])
            same_slot = _slot_kind(left) == _slot_kind(right)
            same_group_identical = bool(left.get("group_id") and left.get("group_id") == right.get("group_id") and iou == 1.0)
            stack_allowed = bool(left.get("stack_allowed") or right.get("stack_allowed"))
            if iou > iou_threshold and (same_slot or (same_group_identical and not stack_allowed)):
                collisions.append(
                    {
                        "rule": "same_semantic_role_sibling" if same_slot else "same_group_child_identical_bbox",
                        "object_ids": [left["object_id"], right["object_id"]],
                        "semantic_roles": [left.get("semantic_role"), right.get("semantic_role")],
                        "slot_kind": _slot_kind(left),
                        "iou": iou,
                        "bbox_norm": left["bbox_norm"],
                    }
                )
    visibility = _visibility_rows(normalized, iou_threshold=iou_threshold)
    visible_counts: dict[str, int] = {}
    declared_counts: dict[str, int] = {}
    for row in visibility:
        slot_kind = row["slot_kind"]
        declared_counts[slot_kind] = declared_counts.get(slot_kind, 0) + 1
        if row["render_visibility"] == "visible":
            visible_counts[slot_kind] = visible_counts.get(slot_kind, 0) + 1
    return {
        "schema_name": "duplicate_bbox_collision_report",
        "status": "passed" if not collisions else "failed",
        "iou_threshold": iou_threshold,
        "collision_count": len(collisions),
        "collisions": collisions,
        "declared_counts": declared_counts,
        "visible_counts": visible_counts,
        "visibility": visibility,
        "failure_codes": sorted({collision["rule"] for collision in collisions}),
        "canva_parity_claimed": False,
    }


def bbox_iou(left: Any, right: Any) -> float:
    a = normalize_bbox(left)
    b = normalize_bbox(right)
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    iw = max(0.0, min(ax2, bx2) - max(a["x"], b["x"]))
    ih = max(0.0, min(ay2, by2) - max(a["y"], b["y"]))
    intersection = iw * ih
    union = a["w"] * a["h"] + b["w"] * b["h"] - intersection
    return round(intersection / union, 6) if union else 0.0


def normalize_bbox(value: Any) -> dict[str, float]:
    if isinstance(value, dict):
        return {key: round(float(value[key]), 6) for key in ("x", "y", "w", "h")}
    if isinstance(value, (list, tuple)) and len(value) == 4:
        x1, y1, x2_or_w, y2_or_h = [float(item) for item in value]
        if x2_or_w > x1 and y2_or_h > y1:
            return {"x": round(x1, 6), "y": round(y1, 6), "w": round(x2_or_w - x1, 6), "h": round(y2_or_h - y1, 6)}
        return {"x": round(x1, 6), "y": round(y1, 6), "w": round(x2_or_w, 6), "h": round(y2_or_h, 6)}
    raise ValueError(f"Unsupported bbox: {value!r}")


def _visibility_rows(records: list[dict[str, Any]], *, iou_threshold: float) -> list[dict[str, Any]]:
    visible_by_slot: dict[str, list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: (item.get("z_order", 0), item["object_id"])):
        slot_kind = _slot_kind(record)
        occluder = next((seen for seen in visible_by_slot.get(slot_kind, []) if bbox_iou(record["bbox_norm"], seen["bbox_norm"]) > iou_threshold), None)
        if occluder:
            visibility = "occluded_by_duplicate_bbox"
            occluded_by = occluder["object_id"]
        else:
            visibility = "visible"
            occluded_by = None
            visible_by_slot.setdefault(slot_kind, []).append(record)
        rows.append(
            {
                "object_id": record["object_id"],
                "semantic_role": record.get("semantic_role"),
                "slot_kind": slot_kind,
                "bbox_norm": record["bbox_norm"],
                "render_visibility": visibility,
                "occluded_by": occluded_by,
            }
        )
    return rows


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    object_id = str(record.get("object_id") or record.get("shape_name") or record.get("id") or "")
    normalized = dict(record)
    normalized["object_id"] = object_id
    normalized["bbox_norm"] = normalize_bbox(record["bbox_norm"])
    return normalized


def _slot_kind(record: dict[str, Any]) -> str:
    object_id = str(record.get("object_id", ""))
    role = str(record.get("semantic_role") or "")
    if object_id.startswith("card_text") or role == "body_text_region":
        return "card_text"
    if object_id.startswith("kpi_text") or role == "kpi_text_region":
        return "kpi_text"
    if object_id.startswith("card_panel") or role == "card_panel":
        return "card_panel"
    if role == "source_footer_text":
        return "source_footer_text"
    return role or object_id
