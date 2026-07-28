"""Contract V2 helpers for the isolated run_002 four-core gate."""

from __future__ import annotations

from typing import Any


ARCHETYPES: tuple[str, ...] = ("cover_hero", "standard_content", "data_dashboard", "table_heavy")

_SLOT_DEFS: dict[str, list[dict[str, Any]]] = {
    "cover_hero": [
        {"slot_id": "title", "slot_type": "title", "min": 12, "max": 54, "actual": "title"},
        {"slot_id": "subtitle", "slot_type": "subtitle", "min": 12, "max": 96, "actual": "subtitle"},
        {"slot_id": "hero_image", "slot_type": "image_frame", "min": 0, "max": 0, "actual": "hero_image", "allowed": ["image_frame", "ppt_shape"]},
        {"slot_id": "meta_bar", "slot_type": "callout", "min": 8, "max": 42, "actual": "date_presenter"},
        {"slot_id": "footer_or_source_strip", "slot_type": "source_strip", "min": 8, "max": 120, "actual": "footer"},
    ],
    "standard_content": [
        {"slot_id": "title", "slot_type": "title", "min": 12, "max": 72, "actual": "title"},
        {"slot_id": "body_or_card_group", "slot_type": "card", "min": 120, "max": 520, "actual": "cards", "allowed": ["ppt_text", "ppt_shape"]},
        {"slot_id": "takeaway_or_insight", "slot_type": "callout", "min": 16, "max": 120, "actual": "insight_takeaway"},
        {"slot_id": "footer_or_source_strip", "slot_type": "source_strip", "min": 8, "max": 120, "actual": "footer"},
    ],
    "data_dashboard": [
        {"slot_id": "title", "slot_type": "title", "min": 12, "max": 72, "actual": "title"},
        {"slot_id": "kpi_cards", "slot_type": "card", "min": 40, "max": 180, "actual": "kpi_cards"},
        {"slot_id": "primary_chart", "slot_type": "chart", "min": 0, "max": 80, "actual": "primary_chart", "allowed": ["ppt_chart", "ppt_shape"]},
        {"slot_id": "insight_box_or_secondary_chart", "slot_type": "chart", "min": 0, "max": 100, "actual": "secondary_chart", "allowed": ["ppt_chart", "ppt_shape", "ppt_text"]},
        {"slot_id": "source_strip", "slot_type": "source_strip", "min": 8, "max": 120, "actual": "footer"},
    ],
    "table_heavy": [
        {"slot_id": "title", "slot_type": "title", "min": 12, "max": 72, "actual": "title"},
        {"slot_id": "table_region", "slot_type": "table", "min": 0, "max": 0, "actual": "table", "allowed": ["ppt_table", "ppt_shape"]},
        {"slot_id": "source_strip", "slot_type": "source_strip", "min": 8, "max": 120, "actual": "footer"},
        {"slot_id": "optional_kpi_or_note", "slot_type": "card", "min": 8, "max": 96, "actual": "kpi_chips"},
    ],
}

_PROTECTED_BBOXES = {
    "title": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.22},
    "subtitle": {"x": 0.0, "y": 0.22, "w": 0.52, "h": 0.38},
    "body_or_card_group": {"x": 0.0, "y": 0.24, "w": 1.0, "h": 0.6},
    "takeaway_or_insight": {"x": 0.0, "y": 0.68, "w": 1.0, "h": 0.16},
    "kpi_cards": {"x": 0.0, "y": 0.18, "w": 1.0, "h": 0.18},
    "primary_chart": {"x": 0.0, "y": 0.34, "w": 0.62, "h": 0.5},
    "insight_box_or_secondary_chart": {"x": 0.62, "y": 0.34, "w": 0.38, "h": 0.5},
    "table_region": {"x": 0.0, "y": 0.28, "w": 1.0, "h": 0.58},
    "hero_image": {"x": 0.52, "y": 0.14, "w": 0.44, "h": 0.64},
    "meta_bar": {"x": 0.0, "y": 0.68, "w": 0.5, "h": 0.1},
    "footer_or_source_strip": {"x": 0.0, "y": 0.86, "w": 1.0, "h": 0.14},
    "source_strip": {"x": 0.0, "y": 0.86, "w": 1.0, "h": 0.14},
    "optional_kpi_or_note": {"x": 0.48, "y": 0.12, "w": 0.48, "h": 0.12},
}


def build_template_contract_v2(
    *,
    archetype_id: str,
    design_reading: dict[str, Any] | None = None,
    editable_master_spec: dict[str, Any] | None = None,
    legacy_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if archetype_id not in _SLOT_DEFS:
        raise ValueError(f"unsupported run_002 4-core archetype: {archetype_id}")
    slots = [_slot_contract(defn) for defn in _SLOT_DEFS[archetype_id]]
    required_slots = [slot["slot_id"] for slot in slots]
    return {
        "$schema": "../../../../../../schemas/template_contract_v2.schema.json",
        "contract_version": "2",
        "archetype_id": archetype_id,
        "layout_id": f"run_002_{archetype_id}_contract_v2_master",
        "required_slots": required_slots,
        "slot_contracts": slots,
        "editable_object_assertions": {
            "all_real_text_is_ppt_text": True,
            "cards_are_ppt_shapes": True,
            "panels_are_ppt_shapes": True,
            "dividers_are_ppt_shapes": True,
            "footer_is_ppt_shapes_or_text": True,
            "source_strip_is_editable": True,
            "semantic_icons_are_svg_or_vector": True,
            "semantic_tables_are_native_or_editable_shape_grid": True,
            "semantic_charts_are_native_or_editable_shape_chart": True,
            "hero_photo_is_replaceable_frame": True,
            "reference_image_not_embedded_as_background": True,
        },
        "semantic_component_assertions": {
            "icons": "svg_or_vector",
            "tables": "native_or_editable_shape_grid",
            "charts": "native_or_editable_shape_chart",
            "cards": "ppt_shape_groups",
            "kpi_cards": "editable_component_groups",
            "text": "ppt_text",
        },
        "asset_policy": {
            "reference_images_allowed_as_design_inputs_only": True,
            "reference_images_may_be_embedded": False,
            "semantic_svg_icons_required": True,
        },
        "raster_policy": {
            "full_slide_raster_allowed": False,
            "content_bearing_raster_allowed": False,
            "photo_frame_raster_allowed": True,
            "texture_raster_allowed": "allowlisted_only",
            "semantic_component_raster_allowed": False,
        },
        "fallback_policy": {
            "fallback_allowed": False,
            "semantic_component_fallback_allowed": False,
            "all_fallbacks_must_be_recorded": True,
            "unrecorded_fallback_is_fatal": True,
            "raster_fallback_requires_allowlist": True,
        },
        "overflow_policy": {
            "text_overflow_allowed": False,
            "unbounded_placeholder_content_allowed": False,
            "source_bound_stage_overflow_must_fail": True,
        },
        "protected_zones": [
            {"zone_id": f"{slot_id}_safe", "bbox": _PROTECTED_BBOXES.get(slot_id, {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}), "intrusion_allowed": False}
            for slot_id in required_slots
        ],
        "source_binding_requirements": {
            "required_for_content_slides": True,
            "required_slot_types": _source_required_slot_types(archetype_id),
            "template_stage_placeholder_allowed": True,
            "source_bound_stage_requirement_declared_for": "B05",
        },
        "citation_binding_requirements": {
            "required_for_content_slides": True,
            "required_slot_types": _source_required_slot_types(archetype_id),
            "template_stage_placeholder_allowed": True,
            "source_bound_stage_requirement_declared_for": "B05",
        },
        "render_policy": {
            "render_required": False,
            "renderer_skip_allowed": True,
            "structural_ledger_required_if_render_skipped": True,
        },
        "structural_ledger_requirements": {
            "required": True,
            "min_slide_count": 1,
            "require_object_ledger": True,
        },
        "warning_policy": {
            "allowlist": [],
        },
        "qa_policy": {
            "qa_report_required": True,
            "zero_unallowlisted_warnings": True,
            "selected_route_required": "editable_template",
        },
        "template_stage_policy": {
            "semantic_placeholders_allowed": True,
            "placeholder_text_must_not_be_final_content": True,
            "source_citation_binding_deferred_to_source_bound_stage": True,
        },
        "component_binding": {
            slot["slot_id"]: {"actual_slot_id": _SLOT_DEFS[archetype_id][index]["actual"]}
            for index, slot in enumerate(slots)
        },
        "evidence": {
            "design_reading_present": design_reading is not None,
            "editable_master_spec_present": editable_master_spec is not None,
            "legacy_contract_present": legacy_contract is not None,
        },
    }


def build_component_binding_spec(archetype_id: str) -> dict[str, Any]:
    if archetype_id not in _SLOT_DEFS:
        raise ValueError(f"unsupported run_002 4-core archetype: {archetype_id}")
    return {
        "schema_name": "run_002_component_binding_spec",
        "schema_version": "1.0",
        "archetype_id": archetype_id,
        "contract_version": "2",
        "bindings": [
            {
                "contract_slot_id": item["slot_id"],
                "source_slot_id": item["actual"],
                "slot_type": item["slot_type"],
                "template_stage_placeholder_allowed": True,
                "source_bound_binding_required_later": item["slot_type"] in set(_source_required_slot_types(archetype_id)),
            }
            for item in _SLOT_DEFS[archetype_id]
        ],
    }


def build_template_stage_blueprint(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "slide_id": f"{contract['archetype_id']}-template-stage",
        "template_stage": True,
        "slots": [
            {
                "slot_id": slot["slot_id"],
                "primitive": _blueprint_primitive(slot),
                "editable": True,
                "placeholder_status": "semantic_template_placeholder",
                "text": _placeholder_text(slot),
                "object_id": f"{slot['slot_id']}_template_placeholder",
            }
            for slot in contract["slot_contracts"]
            if slot["required"]
        ],
    }


def _slot_contract(defn: dict[str, Any]) -> dict[str, Any]:
    allowed = defn.get("allowed") or ["ppt_text", "ppt_shape"]
    return {
        "slot_id": defn["slot_id"],
        "slot_type": defn["slot_type"],
        "required": True,
        "editable_required": True,
        "min_capacity_chars": int(defn["min"]),
        "max_capacity_chars": int(defn["max"]),
        "overflow_allowed": False,
        "allowed_primitives": allowed,
        "forbidden_primitives": ["raster_image", "full_slide_raster"],
        "source_binding_required": False,
        "citation_binding_required": False,
        "protected_zone_id": f"{defn['slot_id']}_safe",
        "fallback_allowed": False,
        "fallback_allowlist": [],
        "template_stage_placeholder_allowed": True,
        "actual_run_002_slot_id": defn["actual"],
    }


def _source_required_slot_types(archetype_id: str) -> list[str]:
    if archetype_id == "cover_hero":
        return ["source_strip"]
    if archetype_id == "standard_content":
        return ["card", "callout", "source_strip"]
    if archetype_id == "data_dashboard":
        return ["card", "chart", "source_strip"]
    if archetype_id == "table_heavy":
        return ["table", "card", "source_strip"]
    return ["body", "source_strip"]


def _blueprint_primitive(slot: dict[str, Any]) -> str:
    if slot["slot_type"] == "table":
        return "ppt_table"
    if slot["slot_type"] == "chart":
        return "ppt_chart"
    if slot["slot_type"] == "image_frame":
        return "image_frame"
    return "ppt_text"


def _placeholder_text(slot: dict[str, Any]) -> str:
    if slot["max_capacity_chars"] == 0:
        return ""
    text = slot["slot_id"].replace("_", " ").upper()
    return text[: max(1, min(len(text), int(slot["max_capacity_chars"])))]
