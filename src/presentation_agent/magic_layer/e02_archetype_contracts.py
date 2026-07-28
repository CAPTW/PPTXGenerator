"""Strict E02 four-core archetype contracts and local design intents."""

from __future__ import annotations

from typing import Any


CORE_ARCHETYPE_IDS = ("cover_hero", "standard_content", "data_dashboard", "table_heavy")


def build_e02_archetype_contracts() -> dict[str, dict[str, Any]]:
    return {
        "cover_hero": {
            "archetype_id": "cover_hero",
            "required_roles": ["title_text_region", "subtitle_text_region", "hero_visual_field", "source_footer_strip", "source_footer_text"],
            "required_visible_counts": {"title_text_region": 1, "subtitle_text_region": 1, "hero_visual_field": 1, "source_footer_strip": 1},
            "native_component_requirements": {},
            "forbidden": ["full_slide_raster", "screenshot_slide", "semantic_raster_fallback"],
        },
        "standard_content": {
            "archetype_id": "standard_content",
            "required_roles": ["title_text_region", "subtitle_text_region", "card_panel", "body_text_region", "source_footer_strip"],
            "required_visible_counts": {"title_text_region": 1, "subtitle_text_region": 1, "card_panel": 3, "card_text": 3, "source_footer_strip": 1},
            "native_component_requirements": {},
            "forbidden": ["duplicate_semantic_bbox_collision", "full_slide_raster", "semantic_raster_fallback"],
        },
        "data_dashboard": {
            "archetype_id": "data_dashboard",
            "required_roles": ["title_text_region", "kpi_card", "kpi_text_region", "primary_chart", "insight_panel", "source_footer_strip"],
            "required_visible_counts": {"title_text_region": 1, "kpi_card": 3, "kpi_text": 3, "primary_chart": 1, "insight_panel": 1, "source_footer_strip": 1},
            "native_component_requirements": {"primary_chart": "native_chart"},
            "forbidden": ["chart_raster", "chart_not_applicable", "full_slide_raster"],
        },
        "table_heavy": {
            "archetype_id": "table_heavy",
            "required_roles": ["title_text_region", "table_region", "table_header_band", "table_body_grid", "source_footer_strip"],
            "required_visible_counts": {"title_text_region": 1, "table_region": 1, "table_header_band": 1, "table_body_grid": 1, "source_footer_strip": 1},
            "native_component_requirements": {"table_region": "native_table"},
            "forbidden": ["table_raster", "table_not_applicable", "full_slide_raster"],
        },
    }


def build_e02_design_intent_trace(archetype_id: str) -> dict[str, Any]:
    if archetype_id not in CORE_ARCHETYPE_IDS:
        raise ValueError(f"Unknown E02 archetype: {archetype_id}")
    builders = {
        "cover_hero": _cover_hero_slots,
        "standard_content": _standard_content_slots,
        "data_dashboard": _data_dashboard_slots,
        "table_heavy": _table_heavy_slots,
    }
    return {
        "schema_name": "e02_design_intent_trace",
        "archetype": archetype_id,
        "layout_signature": archetype_id,
        "slide_size": {"width_px": 1672, "height_px": 941, "aspect_ratio": "16:9"},
        "style": {
            "maturity": "creative academic professional",
            "palette": ["deep navy", "dark teal", "off-white", "muted gold", "cyan"],
            "deck_feel": "premium consulting template archetype",
            "avoid": "website/SaaS dashboard look",
        },
        "forbidden": ["full_slide_raster", "screenshot_slide", "semantic_raster_fallback", "decorations_over_text", "unreadable_microtext"],
        "slots": builders[archetype_id](),
        "canva_parity_claimed": False,
    }


def validate_archetype_contract(intent: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    roles = [slot["semantic_role"] for slot in intent.get("slots", [])]
    failures: list[str] = []
    for role in contract["required_roles"]:
        if role not in roles:
            failures.append(f"missing_required_role:{role}")
    counts = _slot_counts(intent.get("slots", []))
    for slot_kind, required in contract.get("required_visible_counts", {}).items():
        if counts.get(slot_kind, 0) < required:
            failures.append(f"required_slot_count_low:{slot_kind}")
    if any(_area(slot["bbox_norm_intended"]) >= 0.95 and slot.get("raster_allowed") for slot in intent.get("slots", [])):
        failures.append("full_slide_raster_risk")
    return {
        "schema_name": "e02_archetype_contract_validation",
        "archetype_id": contract["archetype_id"],
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "slot_counts": counts,
        "canva_parity_claimed": False,
    }


def _standard_content_slots() -> list[dict[str, Any]]:
    return [
        _slot("background_base", "background_base", (0, 0, 1, 1), "ppt_shape_background", False, False, 0, 0.95),
        _slot("bg_texture", "decorative_texture", (0.70, 0.04, 0.24, 0.26), "bounded_nonsemantic_raster", False, True, 4, 0.86),
        _slot("hero", "hero_visual_field", (0.63, 0.17, 0.29, 0.55), "replaceable_image_frame", False, True, 12, 0.92),
        _slot("title", "title_text_region", (0.07, 0.10, 0.48, 0.11), "ppt_text_box", True, False, 30, 0.93, min_capacity_chars=54),
        _slot("subtitle", "subtitle_text_region", (0.075, 0.225, 0.44, 0.07), "ppt_text_box", True, False, 31, 0.90, min_capacity_chars=90),
        _slot("card_panel_1", "card_panel", (0.07, 0.36, 0.16, 0.25), "ppt_shape", True, False, 20, 0.90),
        _slot("card_panel_2", "card_panel", (0.255, 0.36, 0.16, 0.25), "ppt_shape", True, False, 20, 0.90),
        _slot("card_panel_3", "card_panel", (0.44, 0.36, 0.16, 0.25), "ppt_shape", True, False, 20, 0.90),
        _slot("card_text_1", "body_text_region", (0.085, 0.40, 0.13, 0.14), "ppt_text_box", True, False, 34, 0.88, min_capacity_chars=80),
        _slot("card_text_2", "body_text_region", (0.27, 0.40, 0.13, 0.14), "ppt_text_box", True, False, 34, 0.88, min_capacity_chars=80),
        _slot("card_text_3", "body_text_region", (0.455, 0.40, 0.13, 0.14), "ppt_text_box", True, False, 34, 0.88, min_capacity_chars=80),
        _slot("semantic_icon_1", "semantic_icon", (0.083, 0.645, 0.047, 0.085), "native_vector", True, False, 35, 0.84),
        _slot("technical_overlay", "technical_overlay", (0.05, 0.78, 0.68, 0.06), "ppt_shape", False, False, 8, 0.78),
        _slot("source_footer_strip", "source_footer_strip", (0.04, 0.91, 0.92, 0.05), "ppt_shape", True, False, 45, 0.92),
        _slot("source_footer_text", "source_footer_text", (0.055, 0.925, 0.60, 0.025), "ppt_text_box", True, False, 46, 0.86, min_capacity_chars=100),
    ]


def _cover_hero_slots() -> list[dict[str, Any]]:
    return [
        _slot("background_base", "background_base", (0, 0, 1, 1), "ppt_shape_background", False, False, 0, 0.95),
        _slot("hero", "hero_visual_field", (0.54, 0.11, 0.38, 0.68), "replaceable_image_frame", False, True, 12, 0.92),
        _slot("title", "title_text_region", (0.07, 0.20, 0.40, 0.18), "ppt_text_box", True, False, 30, 0.93, min_capacity_chars=48),
        _slot("subtitle", "subtitle_text_region", (0.075, 0.43, 0.36, 0.10), "ppt_text_box", True, False, 31, 0.90, min_capacity_chars=90),
        _slot("meta_strip", "meta_text_region", (0.075, 0.60, 0.28, 0.05), "ppt_text_box", True, False, 32, 0.82, min_capacity_chars=40),
        _slot("source_footer_strip", "source_footer_strip", (0.04, 0.91, 0.92, 0.05), "ppt_shape", True, False, 45, 0.92),
        _slot("source_footer_text", "source_footer_text", (0.055, 0.925, 0.60, 0.025), "ppt_text_box", True, False, 46, 0.86, min_capacity_chars=100),
    ]


def _data_dashboard_slots() -> list[dict[str, Any]]:
    return [
        _slot("background_base", "background_base", (0, 0, 1, 1), "ppt_shape_background", False, False, 0, 0.95),
        _slot("title", "title_text_region", (0.06, 0.08, 0.56, 0.10), "ppt_text_box", True, False, 30, 0.93),
        _slot("subtitle", "subtitle_text_region", (0.065, 0.19, 0.46, 0.05), "ppt_text_box", True, False, 31, 0.88),
        _slot("kpi_card_1", "kpi_card", (0.06, 0.30, 0.16, 0.16), "ppt_shape", True, False, 18, 0.88),
        _slot("kpi_card_2", "kpi_card", (0.245, 0.30, 0.16, 0.16), "ppt_shape", True, False, 18, 0.88),
        _slot("kpi_card_3", "kpi_card", (0.43, 0.30, 0.16, 0.16), "ppt_shape", True, False, 18, 0.88),
        _slot("kpi_text_1", "kpi_text_region", (0.075, 0.325, 0.13, 0.08), "ppt_text_box", True, False, 34, 0.88),
        _slot("kpi_text_2", "kpi_text_region", (0.26, 0.325, 0.13, 0.08), "ppt_text_box", True, False, 34, 0.88),
        _slot("kpi_text_3", "kpi_text_region", (0.445, 0.325, 0.13, 0.08), "ppt_text_box", True, False, 34, 0.88),
        _slot("primary_chart", "primary_chart", (0.06, 0.52, 0.52, 0.31), "native_chart", True, False, 28, 0.90),
        _slot("insight_panel", "insight_panel", (0.64, 0.22, 0.28, 0.46), "ppt_shape", True, False, 22, 0.86),
        _slot("insight_text", "insight_text_region", (0.665, 0.27, 0.23, 0.27), "ppt_text_box", True, False, 35, 0.84),
        _slot("source_footer_strip", "source_footer_strip", (0.04, 0.91, 0.92, 0.05), "ppt_shape", True, False, 45, 0.92),
        _slot("source_footer_text", "source_footer_text", (0.055, 0.925, 0.60, 0.025), "ppt_text_box", True, False, 46, 0.86),
    ]


def _table_heavy_slots() -> list[dict[str, Any]]:
    return [
        _slot("background_base", "background_base", (0, 0, 1, 1), "ppt_shape_background", False, False, 0, 0.95),
        _slot("title", "title_text_region", (0.06, 0.08, 0.56, 0.10), "ppt_text_box", True, False, 30, 0.93),
        _slot("subtitle", "subtitle_text_region", (0.065, 0.19, 0.46, 0.05), "ppt_text_box", True, False, 31, 0.88),
        _slot("table_region", "table_region", (0.06, 0.30, 0.70, 0.50), "native_table", True, False, 26, 0.91),
        _slot("table_header_band", "table_header_band", (0.06, 0.30, 0.70, 0.07), "ppt_shape", True, False, 27, 0.88),
        _slot("table_body_grid", "table_body_grid", (0.06, 0.37, 0.70, 0.43), "ppt_shape", True, False, 28, 0.88),
        _slot("kpi_chip_1", "kpi_chip", (0.80, 0.33, 0.12, 0.06), "ppt_shape", True, False, 20, 0.80),
        _slot("source_footer_strip", "source_footer_strip", (0.04, 0.91, 0.92, 0.05), "ppt_shape", True, False, 45, 0.92),
        _slot("source_footer_text", "source_footer_text", (0.055, 0.925, 0.60, 0.025), "ppt_text_box", True, False, 46, 0.86),
    ]


def _slot(
    slot_id: str,
    role: str,
    bbox: tuple[float, float, float, float],
    target: str,
    semantic_allowed: bool,
    raster_allowed: bool,
    z_order: int,
    confidence: float,
    *,
    min_capacity_chars: int | None = None,
) -> dict[str, Any]:
    slot: dict[str, Any] = {
        "slot_id": slot_id,
        "semantic_role": role,
        "bbox_norm_intended": {"x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3]},
        "primitive_target": target,
        "editable_required": True,
        "raster_allowed": raster_allowed,
        "semantic_content_allowed": semantic_allowed,
        "z_order_intended": z_order,
        "confidence": confidence,
    }
    if min_capacity_chars is not None:
        slot["min_capacity_chars"] = min_capacity_chars
    return slot


def _slot_counts(slots: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for slot in slots:
        kind = _slot_kind(slot)
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _slot_kind(slot: dict[str, Any]) -> str:
    role = slot["semantic_role"]
    slot_id = slot["slot_id"]
    if slot_id.startswith("card_text") or role == "body_text_region":
        return "card_text"
    if slot_id.startswith("kpi_text") or role == "kpi_text_region":
        return "kpi_text"
    return role


def _area(bbox: dict[str, float]) -> float:
    return float(bbox["w"]) * float(bbox["h"])
