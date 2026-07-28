"""JSON-first layout contract schema and coordinate policies for E06.1."""

from __future__ import annotations

from typing import Any


REQUIRED_OBJECT_FIELDS = (
    "object_id",
    "slide_id",
    "archetype_id",
    "object_type",
    "semantic_role",
    "component_id",
    "bbox_norm",
    "bbox_in",
    "bbox_emu",
    "z_order",
    "editable",
    "content_bearing",
    "source_binding_id",
    "citation_binding_id",
    "constraints",
)


def build_layout_contract_schema_v1() -> dict[str, Any]:
    return {
        "schema_name": "layout_contract_schema_v1",
        "coordinate_spaces": {
            "normalized": "0..1 relative to slide width and height",
            "inches": "PowerPoint inches",
            "emu": "PowerPoint English Metric Units used by OOXML",
        },
        "slide_required_fields": [
            "slide_id",
            "slide_number",
            "archetype_id",
            "slide_size",
            "objects",
            "semantic_icon_slots",
            "text_zones",
            "source_footer_regions",
            "z_order",
        ],
        "object_required_fields": list(REQUIRED_OBJECT_FIELDS),
        "supported_object_types": [
            "shape",
            "line",
            "text",
            "semantic_icon",
            "icon_background",
            "source_footer",
            "chart_region",
            "table_region",
            "card_region",
            "image_field",
            "decorative",
        ],
        "thresholds": {
            "component_bbox_diff_norm_max": 0.005,
            "icon_bbox_diff_norm_max": 0.003,
            "source_footer_bbox_diff_norm_max": 0.005,
            "rendered_major_region_drift_norm_max": 0.02,
            "semantic_z_order_mismatch_max": 0,
            "unanchored_semantic_object_max": 0,
        },
        "fatal_conditions": [
            "unanchored_semantic_object",
            "object_missing_from_contract",
            "contract_object_missing_from_pptx",
            "semantic_z_order_mismatch",
            "icon_size_token_violation",
            "text_collision",
            "source_footer_coordinate_failure",
        ],
    }


def build_icon_size_token_policy_v2() -> dict[str, Any]:
    tokens = {
        "icon_header_micro": (0.12, 0.18, 0.16),
        "icon_meta_bar": (0.18, 0.30, 0.24),
        "icon_footer_source": (0.14, 0.22, 0.18),
        "icon_table_header": (0.12, 0.20, 0.18),
        "icon_table_status": (0.12, 0.20, 0.18),
        "icon_kpi": (0.18, 0.28, 0.24),
        "icon_card_small": (0.20, 0.30, 0.26),
        "icon_card_primary": (0.28, 0.44, 0.34),
        "icon_side_rail": (0.24, 0.40, 0.30),
        "icon_process_node": (0.18, 0.32, 0.24),
        "icon_timeline_marker": (0.14, 0.24, 0.20),
        "icon_decision_marker": (0.22, 0.36, 0.30),
        "icon_risk_status": (0.22, 0.36, 0.30),
        "icon_note_insight": (0.20, 0.36, 0.30),
        "icon_case_image_callout": (0.20, 0.32, 0.26),
    }
    return {
        "schema_name": "icon_size_token_policy_v2",
        "tokens": {
            token: {
                "min_w_in": values[0],
                "max_w_in": values[1],
                "preferred_w_in": values[2],
                "min_h_in": values[0],
                "max_h_in": values[1],
                "preferred_h_in": values[2],
                "allowed_slot_types": _allowed_slots_for_token(token),
                "contrast_target": "WCAG-like local contrast; measured in rendered gate",
                "collision_padding_in": 0.03,
            }
            for token, values in tokens.items()
        },
        "slot_type_to_token": {
            "header_micro_icon": "icon_header_micro",
            "meta_bar_icon": "icon_meta_bar",
            "source_footer_icon": "icon_footer_source",
            "citation_icon": "icon_footer_source",
            "table_header_icon": "icon_table_header",
            "table_row_status_icon": "icon_table_status",
            "kpi_icon": "icon_kpi",
            "card_status_icon": "icon_card_small",
            "card_corner_badge_icon": "icon_card_small",
            "card_lead_icon": "icon_card_small",
            "title_badge_icon": "icon_card_primary",
            "side_rail_icon": "icon_side_rail",
            "process_node_icon": "icon_process_node",
            "timeline_milestone_icon": "icon_timeline_marker",
            "decision_marker_icon": "icon_decision_marker",
            "risk_status_icon": "icon_risk_status",
            "note_insight_icon": "icon_note_insight",
            "image_callout_icon": "icon_case_image_callout",
        },
        "semantic_icons_should_not_share_single_size": True,
    }


def build_icon_anchor_policy_v2() -> dict[str, Any]:
    slot_types = [
        "header_micro_icon",
        "title_badge_icon",
        "meta_bar_icon",
        "card_lead_icon",
        "card_status_icon",
        "card_corner_badge_icon",
        "kpi_icon",
        "chart_marker_icon",
        "table_header_icon",
        "table_row_status_icon",
        "side_rail_icon",
        "timeline_milestone_icon",
        "process_node_icon",
        "decision_marker_icon",
        "risk_status_icon",
        "source_footer_icon",
        "citation_icon",
        "note_insight_icon",
        "image_callout_icon",
    ]
    return {
        "schema_name": "icon_anchor_policy_v2",
        "fatal_unanchored_semantic_object": True,
        "slot_policies": {
            slot: {
                "anchor_component_type": _anchor_component_type(slot),
                "anchor_position": _anchor_position(slot),
                "padding_in": 0.05 if "table" not in slot else 0.03,
                "alignment_rule": "inside anchor component, optically centered for glyph bbox",
                "optical_correction_allowed": True,
                "z_order_level": "above component background and below foreground text when decorative; above text only for status badges",
                "collision_policy": "no overlap with text/source/citation data bboxes",
            }
            for slot in slot_types
        },
    }


def build_component_coordinate_policy_v1() -> dict[str, Any]:
    return {
        "schema_name": "component_coordinate_policy_v1",
        "source_of_truth": "layout_contract_16_slides.json",
        "bbox_diff_norm_max": 0.005,
        "major_region_render_drift_norm_max": 0.02,
        "required_component_classes": [
            "card_region",
            "table_region",
            "chart_region",
            "source_footer",
            "semantic_icon",
            "text",
            "image_field",
        ],
        "unanchored_semantic_object_policy": "fatal",
    }


def build_z_order_policy_v1() -> dict[str, Any]:
    return {
        "schema_name": "z_order_policy_v1",
        "semantic_z_order_mismatch_max": 0,
        "rules": [
            "background below regions",
            "region/card/table backgrounds below content",
            "semantic SVG icons above their local component background",
            "source/footer/citation text above footer strip",
            "QA/debug overlays excluded from final baseline candidate",
        ],
    }


def build_text_capacity_coordinate_policy_v1() -> dict[str, Any]:
    return {
        "schema_name": "text_capacity_coordinate_policy_v1",
        "text_overflow_max": 0,
        "text_clipping_max": 0,
        "text_collision_max": 0,
        "minimum_visible_font_pt": 6.0,
        "coordinate_requirement": "text bbox must stay within declared component or slot bbox",
    }


def build_source_footer_coordinate_policy_v1() -> dict[str, Any]:
    return {
        "schema_name": "source_footer_coordinate_policy_v1",
        "source_footer_bbox_diff_norm_max": 0.005,
        "rendered_source_footer_drift_norm_max": 0.02,
        "required": True,
        "citation_binding_required": True,
        "source_binding_required": True,
    }


def validate_layout_contract(contract: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    slides = contract.get("slides", [])
    for slide in slides:
        for field in build_layout_contract_schema_v1()["slide_required_fields"]:
            if field not in slide:
                failures.append({"slide_id": slide.get("slide_id"), "failure": f"missing_slide_field:{field}"})
        for obj in slide.get("objects", []):
            for field in REQUIRED_OBJECT_FIELDS:
                if field not in obj:
                    failures.append({"object_id": obj.get("object_id"), "failure": f"missing_object_field:{field}"})
            if not _valid_bbox(obj.get("bbox_norm")):
                failures.append({"object_id": obj.get("object_id"), "failure": "invalid_bbox_norm"})
            if not _valid_bbox(obj.get("bbox_in")):
                failures.append({"object_id": obj.get("object_id"), "failure": "invalid_bbox_in"})
    passed = bool(slides) and not failures
    return {
        "schema_name": "layout_contract_validation_report",
        "status": "passed" if passed else "failed",
        "slide_count": len(slides),
        "object_count": sum(len(slide.get("objects", [])) for slide in slides),
        "semantic_icon_count": sum(len(slide.get("semantic_icon_slots", [])) for slide in slides),
        "failure_count": len(failures),
        "failures": failures,
    }


def _valid_bbox(value: Any) -> bool:
    return isinstance(value, dict) and all(key in value and isinstance(value[key], (int, float)) for key in ("x", "y", "w", "h"))


def _allowed_slots_for_token(token: str) -> list[str]:
    return {
        "icon_header_micro": ["header_micro_icon"],
        "icon_meta_bar": ["meta_bar_icon"],
        "icon_footer_source": ["source_footer_icon", "citation_icon"],
        "icon_table_header": ["table_header_icon"],
        "icon_table_status": ["table_row_status_icon"],
        "icon_kpi": ["kpi_icon"],
        "icon_card_small": ["card_lead_icon", "card_status_icon", "card_corner_badge_icon"],
        "icon_card_primary": ["title_badge_icon", "card_lead_icon"],
        "icon_side_rail": ["side_rail_icon"],
        "icon_process_node": ["process_node_icon"],
        "icon_timeline_marker": ["timeline_milestone_icon"],
        "icon_decision_marker": ["decision_marker_icon", "title_badge_icon"],
        "icon_risk_status": ["risk_status_icon"],
        "icon_note_insight": ["note_insight_icon"],
        "icon_case_image_callout": ["image_callout_icon"],
    }[token]


def _anchor_component_type(slot: str) -> str:
    if "table" in slot:
        return "table_cell_or_header"
    if "card" in slot:
        return "card"
    if "timeline" in slot:
        return "timeline_milestone"
    if "process" in slot:
        return "process_node"
    if "source" in slot or "citation" in slot:
        return "footer_source_region"
    if "meta" in slot:
        return "title_meta_bar"
    return "semantic_component"


def _anchor_position(slot: str) -> str:
    if slot in {"table_header_icon", "source_footer_icon", "citation_icon"}:
        return "inline_before_text"
    if slot in {"card_corner_badge_icon", "decision_marker_icon", "risk_status_icon"}:
        return "badge_corner"
    if slot in {"timeline_milestone_icon", "process_node_icon"}:
        return "center"
    return "center_left"
