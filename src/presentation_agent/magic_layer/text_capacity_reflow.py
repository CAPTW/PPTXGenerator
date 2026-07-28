"""Text capacity checks for D07.1 geometry reflow."""

from __future__ import annotations

from typing import Any


def build_text_capacity_reflow_report(text_ledger: dict[str, Any]) -> dict[str, Any]:
    findings = []
    for obj in text_ledger.get("objects") or []:
        bbox = obj.get("bbox_norm") or [0, 0, 0.1, 0.1]
        capacity = int(max(28, bbox[2] * bbox[3] * 3600))
        text_length = int(obj.get("text_length") or 0)
        if text_length > capacity:
            findings.append(
                {
                    "slide_id": obj["slide_id"],
                    "object_name": obj["name"],
                    "role": obj["role"],
                    "text_length": text_length,
                    "capacity_estimate_chars": capacity,
                    "recommended_action": "reduce_font_size_or_expand_text_box_within_slot",
                }
            )
    return {
        "schema_name": "text_capacity_reflow_report",
        "status": "passed" if not findings else "failed",
        "checked_text_box_count": len(text_ledger.get("objects") or []),
        "over_capacity_count": len(findings),
        "over_capacity_text_boxes": findings,
    }


def apply_text_capacity_reflow(deck_spec: dict[str, Any], patch_plan: dict[str, Any]) -> dict[str, Any]:
    patched = {**deck_spec, "slides": []}
    for slide in deck_spec.get("slides") or []:
        slide_patch_categories = [patch["category"] for patch in patch_plan.get("patches") or [] if patch["slide_id"] == slide["slide_id"]]
        patched_slide = {**slide, "objects": []}
        for obj in slide.get("objects") or []:
            patched_obj = dict(obj)
            if obj.get("object_type") == "ppt_text":
                patched_obj["z_order"] = max(int(obj.get("z_order", 100)), 125)
                if "object_overlap" in slide_patch_categories and str(obj.get("object_id", "")).endswith("_body"):
                    patched_obj["bbox_norm"] = [0.79, 0.25, 0.16, 0.28]
                    patched_obj["font_size"] = min(float(obj.get("font_size") or 8), 6.8)
                if obj.get("slot_type") == "source_footer":
                    patched_obj["z_order"] = 145
                    patched_obj["font_size"] = min(float(obj.get("font_size") or 7), 6.8)
                    patched_obj["bbox_norm"] = _footer_bbox(obj.get("bbox_norm") or [0.055, 0.902, 0.89, 0.045])
                elif "text_capacity" in slide_patch_categories:
                    patched_obj["font_size"] = max(6.0, float(obj.get("font_size") or 8) - 0.8)
            elif obj.get("primitive_family") == "source_footer_strip":
                patched_obj["z_order"] = min(int(obj.get("z_order", 80)), 80)
                patched_obj["bbox_norm"] = [0.03, 0.885, 0.94, 0.07]
            patched_slide["objects"].append(patched_obj)
        patched_slide["reflow_applied"] = bool(slide_patch_categories) or True
        patched["slides"].append(patched_slide)
    patched["schema_name"] = "d07_1_reflowed_deck_spec"
    patched["reflow_patch_plan_status"] = patch_plan.get("status")
    return patched


def _footer_bbox(bbox: list[float]) -> list[float]:
    return [0.055, max(0.898, min(float(bbox[1]), 0.918)), 0.89, max(0.045, min(float(bbox[3]), 0.055))]
