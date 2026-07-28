"""Text/source/icon collision validation for layout contracts."""

from __future__ import annotations

from typing import Any


def validate_text_collisions(contract: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    near_overlaps: list[dict[str, Any]] = []
    comparisons = 0
    for slide in contract.get("slides", []):
        text_objects = [obj for obj in slide.get("objects", []) if obj.get("object_type") in {"text", "source_footer"} and obj.get("content_bearing")]
        icons = [obj for obj in slide.get("objects", []) if obj.get("object_type") == "semantic_icon"]
        for icon in icons:
            for text in text_objects:
                comparisons += 1
                overlap = _overlap_area(icon.get("bbox_norm", {}), text.get("bbox_norm", {}))
                icon_area = _area(icon.get("bbox_norm", {}))
                overlap_ratio = overlap / icon_area if icon_area else 0.0
                if overlap > 0:
                    row = {
                        "slide_id": slide.get("slide_id"),
                        "icon_object_id": icon.get("object_id"),
                        "text_object_id": text.get("object_id"),
                        "overlap_area_norm": round(overlap, 8),
                        "overlap_ratio_of_icon": round(overlap_ratio, 4),
                    }
                    near_overlaps.append(row)
                    if overlap_ratio >= 0.9 and icon.get("slot_type") not in {"table_header_icon", "table_row_status_icon", "risk_status_icon", "source_footer_icon", "citation_icon"}:
                        failures.append({**row, "failure": "icon_text_collision"})
    return {
        "schema_name": "text_collision_validation_report",
        "status": "passed" if not failures else "failed",
        "comparison_count": comparisons,
        "near_overlap_count": len(near_overlaps),
        "text_collision_failure_count": len(failures),
        "near_overlaps": near_overlaps[:100],
        "failures": failures,
    }


def validate_source_footer_coordinates(contract: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for slide in contract.get("slides", []):
        regions = slide.get("source_footer_regions", [])
        for region in regions:
            bbox = region.get("bbox_norm", {})
            inside = _inside_slide(bbox)
            row = {
                "slide_id": slide.get("slide_id"),
                "object_id": region.get("object_id"),
                "name": region.get("name"),
                "bbox_norm": bbox,
                "inside_slide": inside,
                "status": "passed" if inside else "failed",
            }
            rows.append(row)
            if not inside:
                failures.append({**row, "failure": "source_footer_outside_slide"})
    return {
        "schema_name": "source_footer_validation_report",
        "status": "passed" if rows and not failures else "failed",
        "source_footer_region_count": len(rows),
        "source_footer_coordinate_failure_count": len(failures),
        "rows": rows[:250],
        "failures": failures,
    }


def _overlap_area(a: dict[str, float], b: dict[str, float]) -> float:
    ax1, ay1 = float(a.get("x", 0)), float(a.get("y", 0))
    ax2, ay2 = ax1 + float(a.get("w", 0)), ay1 + float(a.get("h", 0))
    bx1, by1 = float(b.get("x", 0)), float(b.get("y", 0))
    bx2, by2 = bx1 + float(b.get("w", 0)), by1 + float(b.get("h", 0))
    overlap_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    overlap_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    return overlap_w * overlap_h


def _area(bbox: dict[str, float]) -> float:
    return max(0.0, float(bbox.get("w", 0))) * max(0.0, float(bbox.get("h", 0)))


def _inside_slide(bbox: dict[str, float]) -> bool:
    return (
        float(bbox.get("x", -1)) >= 0
        and float(bbox.get("y", -1)) >= 0
        and float(bbox.get("x", 0)) + float(bbox.get("w", 0)) <= 1.002
        and float(bbox.get("y", 0)) + float(bbox.get("h", 0)) <= 1.002
    )
