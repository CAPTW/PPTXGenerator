"""Generate bounded E06.3 contract variants from the layout contract."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


EMU_PER_INCH = 914400
SLIDE_W_IN = 16.0
SLIDE_H_IN = 9.0


def build_contract_variant_plan(opportunity_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "contract_variant_plan",
        "status": "passed" if opportunity_report.get("status") == "passed" else "failed",
        "variants": [
            {
                "variant_id": "variant_a",
                "name": "Conservative readability polish",
                "target_slides": "all plus slides 2/10",
                "parameters": ["source_footer_font_size_delta", "source_footer_y_offset", "icon_anchor_offset"],
                "intent": "Small source/footer and icon optical alignment improvements without major composition changes.",
            },
            {
                "variant_id": "variant_b",
                "name": "Dense data optimization",
                "target_slides": [9, 11, 14],
                "parameters": ["table_row_height_delta", "table_column_width_delta", "side_rail_width_delta", "contrast_token_delta"],
                "intent": "Improve dense table/matrix/register whitespace and hierarchy on the monitored slides.",
            },
            {
                "variant_id": "variant_c",
                "name": "Visual hierarchy improvement",
                "target_slides": [2, 10],
                "parameters": ["title_region_spacing", "card_padding_delta", "chart_region_scale", "icon_anchor_offset", "contrast_token_delta"],
                "intent": "Improve the lowest-scoring TOC and dashboard slides while preserving deck rhythm.",
            },
        ],
        "compile_from_contract_required": True,
        "binding_preservation_required": True,
        "semantic_raster_allowed": False,
    }


def generate_contract_variants(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "variant_a": _variant_a(contract),
        "variant_b": _variant_b(contract),
        "variant_c": _variant_c(contract),
    }


def build_contract_variant_diff_report(baseline: dict[str, Any], variants: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    baseline_bboxes = _bbox_index(baseline)
    for variant_id, variant in variants.items():
        changed = []
        for object_id, bbox in _bbox_index(variant).items():
            if baseline_bboxes.get(object_id) != bbox:
                obj = _object_by_id(variant, object_id)
                changed.append(
                    {
                        "object_id": object_id,
                        "slide_number": obj.get("slide_number"),
                        "object_type": obj.get("object_type"),
                        "semantic_role": obj.get("semantic_role"),
                        "before_bbox_in": baseline_bboxes.get(object_id),
                        "after_bbox_in": bbox,
                    }
                )
        style_changed = [
            obj
            for slide in variant.get("slides", [])
            for obj in slide.get("objects", [])
            if obj.get("style_override_fill_rgb")
        ]
        rows.append(
            {
                "variant_id": variant_id,
                "changed_object_count": len(changed),
                "style_token_override_count": len(style_changed),
                "changed_objects": changed[:80],
            }
        )
    return {
        "schema_name": "contract_variant_diff_report",
        "status": "passed" if all(row["changed_object_count"] > 0 for row in rows) else "failed",
        "variant_count": len(rows),
        "variants": rows,
    }


def _variant_a(contract: dict[str, Any]) -> dict[str, Any]:
    variant = deepcopy(contract)
    _mark(variant, "variant_a", "Conservative readability polish")
    for slide in variant.get("slides", []):
        for obj in slide.get("objects", []):
            name = str(obj.get("name", "")).lower()
            if obj.get("object_type") == "source_footer" and ("source_text" in name or "marker_text" in name):
                _resize(obj, dw=0.08, dh=0.015, anchor="left")
                _shift(obj, dy=-0.01)
                _tag(obj, "source_footer_font_size_delta", "+0.2pt equivalent bbox affordance")
            if int(slide.get("slide_number", 0)) in {2, 10} and obj.get("object_type") == "semantic_icon":
                _shift(obj, dx=0.01, dy=-0.005)
                _tag(obj, "icon_anchor_offset", "+0.01in x, -0.005in y")
    _refresh_indexes(variant)
    return variant


def _variant_b(contract: dict[str, Any]) -> dict[str, Any]:
    variant = deepcopy(contract)
    _mark(variant, "variant_b", "Dense data optimization")
    for slide in variant.get("slides", []):
        if int(slide.get("slide_number", 0)) not in {9, 11, 14}:
            continue
        for obj in slide.get("objects", []):
            name = str(obj.get("name", "")).lower()
            otype = obj.get("object_type")
            if otype in {"table_region", "chart_region"} and any(tok in name for tok in ("grid_r", "grid_cell", "matrix", "risk_register_grid", "table_heavy_grid")):
                _resize(obj, dw=0.012, dh=0.018, anchor="center")
                _tag(obj, "table_row_height_delta", "+0.018in local grid breathing room")
            if otype == "text" and any(tok in name for tok in ("textbox", "matrix", "risk", "table")):
                _resize(obj, dw=0.05, dh=0.012, anchor="left")
                _tag(obj, "table_column_width_delta", "+0.05in text affordance")
            if otype == "source_footer" and ("source_text" in name or "marker_text" in name):
                _resize(obj, dw=0.12, dh=0.02, anchor="left")
                _shift(obj, dy=-0.015)
                _tag(obj, "source_footer_font_size_delta", "+0.25pt equivalent bbox affordance")
            if any(tok in name for tok in ("side_meta_rail", "risk_side_meta_rail")):
                _resize(obj, dw=-0.06, dh=0.0, anchor="right")
                _tag(obj, "side_rail_width_delta", "-0.06in")
    _refresh_indexes(variant)
    return variant


def _variant_c(contract: dict[str, Any]) -> dict[str, Any]:
    variant = deepcopy(contract)
    _mark(variant, "variant_c", "Visual hierarchy improvement")
    for slide in variant.get("slides", []):
        slide_no = int(slide.get("slide_number", 0))
        if slide_no not in {2, 10}:
            continue
        for obj in slide.get("objects", []):
            name = str(obj.get("name", "")).lower()
            otype = obj.get("object_type")
            if otype == "text" and ("title" in name or "side_meta_text" in name):
                _resize(obj, dw=0.16, dh=0.025, anchor="left")
                _tag(obj, "title_region_spacing", "+0.16in width and +0.025in height")
            if otype in {"card_region", "chart_region"} and any(tok in name for tok in ("nav_card", "kpi_", "primary_chart_frame", "insight_panel")):
                _resize(obj, dw=0.025, dh=0.025, anchor="center")
                _apply_contrast(obj, "102A3A")
                _tag(obj, "card_padding_delta", "+0.025in card/chart breathing room")
            if otype == "semantic_icon":
                _shift(obj, dx=0.015, dy=-0.005)
                _tag(obj, "icon_anchor_offset", "+0.015in x, -0.005in y")
            if otype == "source_footer" and ("source_text" in name or "marker_text" in name):
                _resize(obj, dw=0.12, dh=0.02, anchor="left")
                _shift(obj, dy=-0.012)
                _tag(obj, "source_footer_font_size_delta", "+0.25pt equivalent bbox affordance")
            if slide_no == 10 and otype == "chart_region" and "primary_chart_frame" in name:
                _resize(obj, dw=0.08, dh=0.06, anchor="center")
                _tag(obj, "chart_region_scale", "+0.08in width/+0.06in height")
    _refresh_indexes(variant)
    return variant


def _mark(contract: dict[str, Any], variant_id: str, name: str) -> None:
    contract["contract_variant_id"] = variant_id
    contract["contract_variant_name"] = name
    contract["source_of_truth"] = "e06_3_contract_variant"


def _bbox_index(contract: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {
        obj["object_id"]: obj.get("bbox_in", {})
        for slide in contract.get("slides", [])
        for obj in slide.get("objects", [])
        if obj.get("object_id")
    }


def _object_by_id(contract: dict[str, Any], object_id: str) -> dict[str, Any]:
    for slide in contract.get("slides", []):
        for obj in slide.get("objects", []):
            if obj.get("object_id") == object_id:
                merged = dict(obj)
                merged["slide_number"] = slide.get("slide_number")
                return merged
    return {}


def _tag(obj: dict[str, Any], parameter: str, value: str) -> None:
    obj.setdefault("e06_3_tuning_parameters", []).append({"parameter_id": parameter, "value": value})


def _apply_contrast(obj: dict[str, Any], rgb: str) -> None:
    obj["style_override_fill_rgb"] = rgb
    _tag(obj, "contrast_token_delta", f"fill #{rgb}")


def _shift(obj: dict[str, Any], dx: float = 0.0, dy: float = 0.0) -> None:
    bbox = dict(obj.get("bbox_in", {}))
    bbox["x"] = round(float(bbox.get("x", 0.0)) + dx, 6)
    bbox["y"] = round(float(bbox.get("y", 0.0)) + dy, 6)
    _set_bbox(obj, bbox)


def _resize(obj: dict[str, Any], dw: float = 0.0, dh: float = 0.0, *, anchor: str) -> None:
    bbox = dict(obj.get("bbox_in", {}))
    old_w = float(bbox.get("w", 0.0))
    old_h = float(bbox.get("h", 0.0))
    new_w = max(0.01, old_w + dw)
    new_h = max(0.01, old_h + dh)
    if anchor == "center":
        bbox["x"] = round(float(bbox.get("x", 0.0)) - (new_w - old_w) / 2, 6)
        bbox["y"] = round(float(bbox.get("y", 0.0)) - (new_h - old_h) / 2, 6)
    elif anchor == "right":
        bbox["x"] = round(float(bbox.get("x", 0.0)) + (old_w - new_w), 6)
    bbox["w"] = round(new_w, 6)
    bbox["h"] = round(new_h, 6)
    _set_bbox(obj, bbox)


def _set_bbox(obj: dict[str, Any], bbox: dict[str, float]) -> None:
    bbox["x"] = max(0.0, min(SLIDE_W_IN - 0.01, float(bbox.get("x", 0.0))))
    bbox["y"] = max(0.0, min(SLIDE_H_IN - 0.01, float(bbox.get("y", 0.0))))
    bbox["w"] = max(0.01, min(SLIDE_W_IN - bbox["x"], float(bbox.get("w", 0.01))))
    bbox["h"] = max(0.01, min(SLIDE_H_IN - bbox["y"], float(bbox.get("h", 0.01))))
    obj["bbox_in"] = {k: round(v, 6) for k, v in bbox.items()}
    obj["bbox_emu"] = {
        "x": int(round(obj["bbox_in"]["x"] * EMU_PER_INCH)),
        "y": int(round(obj["bbox_in"]["y"] * EMU_PER_INCH)),
        "w": int(round(obj["bbox_in"]["w"] * EMU_PER_INCH)),
        "h": int(round(obj["bbox_in"]["h"] * EMU_PER_INCH)),
    }
    obj["bbox_norm"] = {
        "x": round(obj["bbox_in"]["x"] / SLIDE_W_IN, 6),
        "y": round(obj["bbox_in"]["y"] / SLIDE_H_IN, 6),
        "w": round(obj["bbox_in"]["w"] / SLIDE_W_IN, 6),
        "h": round(obj["bbox_in"]["h"] / SLIDE_H_IN, 6),
    }


def _refresh_indexes(contract: dict[str, Any]) -> None:
    for slide in contract.get("slides", []):
        objects = slide.get("objects", [])
        slide["source_footer_regions"] = [obj for obj in objects if obj.get("object_type") == "source_footer"]
        slide["semantic_icon_slots"] = [obj for obj in objects if obj.get("object_type") == "semantic_icon"]
        slide["text_zones"] = [obj for obj in objects if obj.get("object_type") in {"text", "source_footer"}]
