"""Z-order and protected-zone checks for D07.1 geometry reflow."""

from __future__ import annotations

from typing import Any


def build_z_order_geometry_report(object_ledger: dict[str, Any]) -> dict[str, Any]:
    objects = object_ledger.get("objects") or []
    violations: list[dict[str, Any]] = []
    by_slide: dict[int, list[dict[str, Any]]] = {}
    for obj in objects:
        by_slide.setdefault(int(obj["slide_index"]), []).append(obj)
    for slide_index, slide_objects in by_slide.items():
        footer_strip_z = max((obj["z_order"] for obj in slide_objects if obj["role"] == "source_footer_strip"), default=0)
        footer_text_z = max((obj["z_order"] for obj in slide_objects if obj["role"] == "source_footer_text"), default=0)
        if footer_strip_z and footer_text_z and footer_text_z <= footer_strip_z:
            violations.append(
                {
                    "slide_id": f"d07_slide_{slide_index:02d}",
                    "issue": "Source/citation footer text is not above footer strip.",
                    "footer_strip_z": footer_strip_z,
                    "footer_text_z": footer_text_z,
                }
            )
        for text in [obj for obj in slide_objects if obj["role"] in {"title_text", "subtitle_text", "body_text"}]:
            covering_decorations = [
                obj
                for obj in slide_objects
                if obj["z_order"] > text["z_order"]
                and obj["role"] in {"panel", "visual_object"}
                and _overlap_area(text["bbox_norm"], obj["bbox_norm"]) > 0.002
            ]
            if covering_decorations:
                violations.append(
                    {
                        "slide_id": f"d07_slide_{slide_index:02d}",
                        "issue": f"Decorative object appears above text box {text['name']}.",
                        "text_object": text["name"],
                        "covering_objects": [obj["name"] for obj in covering_decorations],
                    }
                )
    return {
        "schema_name": "z_order_geometry_ledger",
        "status": "passed" if not violations else "failed",
        "violation_count": len(violations),
        "violations": violations,
    }


def build_protected_zone_geometry_report(object_ledger: dict[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    for obj in object_ledger.get("objects") or []:
        slide_id = obj["slide_id"]
        x, y, w, h = obj["bbox_norm"]
        if obj["content_bearing"] and (x < 0.015 or y < 0.015 or x + w > 0.985 or y + h > 0.985):
            violations.append({"slide_id": slide_id, "object_name": obj["name"], "issue": "Content-bearing object outside safe slide margin."})
        if obj["role"] in {"chart", "table"} and y + h > 0.86:
            violations.append({"slide_id": slide_id, "object_name": obj["name"], "issue": "Chart/table intrudes into source footer zone."})
        if obj["role"] == "source_footer_text" and not (0.86 <= y <= 0.95):
            violations.append({"slide_id": slide_id, "object_name": obj["name"], "issue": "Source/citation footer text is outside footer zone."})
    return {
        "schema_name": "protected_zone_geometry_report",
        "status": "passed" if not violations else "failed",
        "violation_count": len(violations),
        "violations": violations,
    }


def build_object_alignment_report(object_ledger: dict[str, Any]) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    by_slide: dict[int, list[dict[str, Any]]] = {}
    for obj in object_ledger.get("objects") or []:
        by_slide.setdefault(int(obj["slide_index"]), []).append(obj)
    for slide_index, slide_objects in by_slide.items():
        cards = [obj for obj in slide_objects if any(token in obj["name"].lower() for token in ["card", "node", "milestone"])]
        if len(cards) >= 3:
            ys = [round(obj["bbox_norm"][1], 2) for obj in cards]
            if len(set(ys)) > 4:
                warnings.append(
                    {
                        "slide_id": f"d07_slide_{slide_index:02d}",
                        "issue": "Card/node group has weak row alignment.",
                        "severity": "LOW_POLISH",
                    }
                )
    return {
        "schema_name": "object_alignment_report",
        "status": "passed",
        "warning_count": len(warnings),
        "warnings": warnings,
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
