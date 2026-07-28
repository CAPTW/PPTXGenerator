"""Human-guided contract adjustments for E06.4."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.presentation_agent.magic_layer.e06_3_contract_variant_generator import _apply_contrast, _refresh_indexes, _resize, _shift, _tag


TARGET_SLIDES = {2, 9, 10, 11, 14}


def build_manual_contract_adjustment_plan() -> dict[str, Any]:
    return {
        "schema_name": "manual_contract_adjustment_plan",
        "status": "passed",
        "adjustments": [
            _adjustment(2, ["active_state_emphasis_token", "card_padding_delta", "icon_anchor_offset"], "Stronger TOC path and scanability."),
            _adjustment(9, ["table_row_height_delta", "table_column_width_delta", "panel_contrast_token"], "Open comparison matrix and status chips."),
            _adjustment(10, ["chart_region_scale", "chart_panel_padding", "card_padding_delta"], "Clearer dashboard chart and KPI hierarchy."),
            _adjustment(11, ["table_row_height_delta", "table_column_width_delta", "source_footer_contrast_token"], "Readable table row/header rhythm."),
            _adjustment(14, ["table_row_height_delta", "panel_contrast_token", "icon_size_token_delta"], "Clearer risk/status hierarchy."),
        ],
        "source_content_change_allowed": False,
        "binding_ids_preserved": True,
    }


def build_human_tuned_contract(selected_contract: dict[str, Any] | None, baseline_contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = deepcopy(selected_contract or baseline_contract)
    contract["contract_variant_id"] = "human_tuned"
    contract["contract_variant_name"] = "E06.4 human-guided target slide tuning"
    contract["source_of_truth"] = "e06_4_human_guided_contract_tuning"
    changes: list[dict[str, Any]] = []
    for slide in contract.get("slides", []):
        slide_no = int(slide.get("slide_number", 0))
        if slide_no not in TARGET_SLIDES:
            continue
        for obj in slide.get("objects", []):
            before = dict(obj.get("bbox_in", {}))
            params_before = len(obj.get("e06_3_tuning_parameters", [])) + len(obj.get("e06_4_tuning_parameters", []))
            _apply_slide_adjustment(slide_no, obj)
            after = dict(obj.get("bbox_in", {}))
            params_after = len(obj.get("e06_3_tuning_parameters", [])) + len(obj.get("e06_4_tuning_parameters", []))
            if before != after or params_after != params_before or obj.get("style_override_fill_rgb"):
                changes.append(
                    {
                        "slide_number": slide_no,
                        "object_id": obj.get("object_id"),
                        "object_type": obj.get("object_type"),
                        "name": obj.get("name"),
                        "before_bbox_in": before,
                        "after_bbox_in": after,
                        "style_override_fill_rgb": obj.get("style_override_fill_rgb"),
                        "parameters": obj.get("e06_4_tuning_parameters", []),
                    }
                )
    _refresh_indexes(contract)
    diff = {
        "schema_name": "layout_contract_human_tuned_diff_report",
        "status": "passed" if changes else "failed",
        "changed_object_count": len(changes),
        "target_slides_changed": sorted({row["slide_number"] for row in changes}),
        "changes": changes[:240],
    }
    return contract, diff


def _adjustment(slide_number: int, controls: list[str], reason: str) -> dict[str, Any]:
    return {
        "slide_number": slide_number,
        "controls": controls,
        "reason": reason,
        "expected_visible_effect": "material contact-sheet-scale improvement",
    }


def _apply_slide_adjustment(slide_no: int, obj: dict[str, Any]) -> None:
    name = str(obj.get("name", "")).lower()
    otype = obj.get("object_type")
    if slide_no == 2:
        if otype == "card_region" and "nav_card" in name:
            _resize(obj, dw=0.18, dh=0.055, anchor="center")
            _e06_4_tag(obj, "card_padding_delta", "+0.18in width/+0.055in height for row scanability")
            if "nav_card_0" in name or "nav_card_1" in name:
                _apply_contrast(obj, "F2EBDD")
                _e06_4_tag(obj, "active_state_emphasis_token", "stronger leading module emphasis")
        if otype == "text" and ("nav_text" in name or "title" in name):
            _resize(obj, dw=0.14, dh=0.03, anchor="left")
            _e06_4_tag(obj, "title_region_spacing", "more readable TOC text region")
        if otype == "semantic_icon":
            _shift(obj, dx=0.025, dy=-0.01)
            _resize(obj, dw=0.025, dh=0.025, anchor="center")
            _e06_4_tag(obj, "icon_anchor_offset", "optical alignment into TOC lead slots")
    elif slide_no == 10:
        if otype == "chart_region" and "primary_chart_frame" in name:
            _resize(obj, dw=0.28, dh=0.18, anchor="center")
            _apply_contrast(obj, "F2EBDD")
            _e06_4_tag(obj, "chart_region_scale", "larger primary data area")
        if otype == "chart_region" and ("kpi_" in name and ("card_native" in name or "label_text" in name or "value_text" in name)):
            _resize(obj, dw=0.08, dh=0.035, anchor="center")
            _e06_4_tag(obj, "card_padding_delta", "KPI card/text breathing room")
        if otype == "semantic_icon":
            _shift(obj, dx=0.018, dy=-0.008)
            _resize(obj, dw=0.02, dh=0.02, anchor="center")
            _e06_4_tag(obj, "icon_anchor_offset", "dashboard icon optical alignment")
        if otype == "source_footer" and ("source_text" in name or "marker_text" in name):
            _resize(obj, dw=0.18, dh=0.025, anchor="left")
            _shift(obj, dy=-0.015)
            _e06_4_tag(obj, "source_footer_font_size_delta", "clearer dashboard footer affordance")
    elif slide_no == 9:
        if otype == "table_region" and any(tok in name for tok in ("grid_r", "grid_cell", "matrix_grid", "score_pill", "chip")):
            _resize(obj, dw=0.03, dh=0.025, anchor="center")
            _e06_4_tag(obj, "table_row_height_delta", "matrix cell breathing room")
            if "score" in name or "pill" in name or "chip" in name:
                _apply_contrast(obj, "17364A")
                _e06_4_tag(obj, "panel_contrast_token", "stronger status chip contrast")
        if otype == "text" and "textbox" in name:
            _resize(obj, dw=0.09, dh=0.025, anchor="left")
            _e06_4_tag(obj, "table_column_width_delta", "comparison label width")
    elif slide_no == 11:
        if otype == "table_region" and any(tok in name for tok in ("grid_cell", "cell_text", "header_cell", "status_pill")):
            _resize(obj, dw=0.02, dh=0.018, anchor="center")
            _e06_4_tag(obj, "table_row_height_delta", "table row/header hierarchy")
            if "header" in name or "status_pill" in name:
                _apply_contrast(obj, "17364A")
                _e06_4_tag(obj, "panel_contrast_token", "table header/status emphasis")
        if otype == "text" and "textbox" in name:
            _resize(obj, dw=0.08, dh=0.02, anchor="left")
            _e06_4_tag(obj, "table_column_width_delta", "readable dense table text")
        if otype == "source_footer" and ("source_text" in name or "marker_text" in name):
            _resize(obj, dw=0.16, dh=0.025, anchor="left")
            _e06_4_tag(obj, "source_footer_contrast_token", "source/footer readability")
    elif slide_no == 14:
        if otype == "table_region" and any(tok in name for tok in ("grid_r", "grid_cell", "score_pill")):
            _resize(obj, dw=0.025, dh=0.022, anchor="center")
            _e06_4_tag(obj, "table_row_height_delta", "risk register row separation")
            if "score_pill" in name:
                _apply_contrast(obj, "17364A")
                _e06_4_tag(obj, "panel_contrast_token", "risk/status chip emphasis")
        if otype == "text" and "textbox" in name:
            _resize(obj, dw=0.08, dh=0.02, anchor="left")
            _e06_4_tag(obj, "table_column_width_delta", "risk register text affordance")
        if otype == "semantic_icon":
            _resize(obj, dw=0.018, dh=0.018, anchor="center")
            _e06_4_tag(obj, "icon_size_token_delta", "risk/status icon legibility")


def _e06_4_tag(obj: dict[str, Any], control: str, value: str) -> None:
    obj.setdefault("e06_4_tuning_parameters", []).append({"control_id": control, "value": value})
    _tag(obj, control, value)
