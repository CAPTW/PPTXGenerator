"""E03 12-core/16-optional archetype registry and design intents."""

from __future__ import annotations

from typing import Any


CORE_12_ARCHETYPE_IDS = (
    "cover_hero",
    "section_divider",
    "visual_toc",
    "standard_content",
    "evidence_overview",
    "card_grid",
    "methodology_framework",
    "process_flow",
    "comparison_matrix",
    "data_dashboard",
    "table_heavy",
    "timeline_roadmap",
)
OPTIONAL_4_ARCHETYPE_IDS = ("photo_caption_grid", "concept_map", "case_study", "closing")


def build_e03_archetype_registry(include_optional: bool = False) -> dict[str, dict[str, Any]]:
    registry = {
        "cover_hero": _entry("Cover Hero", "opening cover", ["title_text_region", "subtitle_text_region", "hero_visual_field", "source_footer_strip"]),
        "section_divider": _entry("Section Divider", "section transition", ["section_number_text_region", "section_title_text_region", "section_subtitle_text_region"]),
        "visual_toc": _entry("Visual TOC", "navigation overview", ["title_text_region", "toc_item", "toc_text_region", "active_marker"]),
        "standard_content": _entry("Standard Content", "three-card content slide", ["title_text_region", "subtitle_text_region", "card_panel", "body_text_region", "source_footer_strip"]),
        "evidence_overview": _entry("Evidence Overview", "claim plus evidence cards", ["title_text_region", "key_claim_text_region", "evidence_card", "evidence_text_region"]),
        "card_grid": _entry("Card Grid", "modular card collection", ["title_text_region", "grid_card", "grid_card_text_region"]),
        "methodology_framework": _entry("Methodology Framework", "framework stages", ["title_text_region", "framework_stage", "framework_text_region", "connector_line"]),
        "process_flow": _entry("Process Flow", "directional process", ["title_text_region", "process_node", "process_text_region", "connector_line"]),
        "comparison_matrix": _entry("Comparison Matrix", "editable matrix", ["title_text_region", "comparison_matrix", "source_footer_strip"], component_requirements={"matrix": "native_table"}),
        "data_dashboard": _entry("Data Dashboard", "KPI plus chart", ["title_text_region", "kpi_card", "kpi_text_region", "primary_chart"], component_requirements={"primary_chart": "native_chart"}),
        "table_heavy": _entry("Table Heavy", "editable table", ["title_text_region", "table_region", "table_header_band", "table_body_grid"], component_requirements={"table_region": "native_table"}),
        "timeline_roadmap": _entry("Timeline Roadmap", "timeline phases", ["title_text_region", "timeline_axis", "timeline_phase", "milestone_text_region"]),
    }
    optional = {
        "photo_caption_grid": _entry("Photo Caption Grid", "image grid with captions", ["title_text_region", "image_frame", "caption_text_region"]),
        "concept_map": _entry("Concept Map", "connected concept nodes", ["central_concept_node", "concept_node", "concept_text_region", "connector_line"]),
        "case_study": _entry("Case Study", "case narrative", ["title_text_region", "case_context_panel", "challenge_text_region", "solution_text_region", "result_text_region"]),
        "closing": _entry("Closing", "closing call to action", ["closing_headline_text_region", "takeaway_text_region", "source_footer_strip"]),
    }
    return {**registry, **optional} if include_optional else registry


def build_e03_design_intent_trace(archetype_id: str) -> dict[str, Any]:
    if archetype_id not in (*CORE_12_ARCHETYPE_IDS, *OPTIONAL_4_ARCHETYPE_IDS):
        raise ValueError(f"Unknown E03 archetype: {archetype_id}")
    slots = _SLOT_BUILDERS[archetype_id]()
    return {
        "schema_name": "e03_design_intent_trace",
        "archetype": archetype_id,
        "layout_signature": f"e03_{archetype_id}",
        "slide_size": {"width_px": 1672, "height_px": 941, "aspect_ratio": "16:9"},
        "style": {
            "maturity": "creative academic professional",
            "palette": ["deep navy", "dark teal", "off-white", "muted gold", "cyan"],
            "deck_feel": "premium reusable editable template pack",
            "avoid": "website/SaaS dashboard look",
        },
        "forbidden": ["full_slide_raster", "screenshot_slide", "semantic_raster_fallback", "decorations_over_text", "unreadable_microtext"],
        "slots": slots,
        "canva_parity_claimed": False,
    }


def required_visible_counts(archetype_id: str) -> dict[str, int]:
    return {
        "cover_hero": {"title_text_region": 1, "subtitle_text_region": 1, "hero_visual_field": 1, "source_footer_strip": 1},
        "section_divider": {"section_number_text_region": 1, "section_title_text_region": 1, "section_subtitle_text_region": 1},
        "visual_toc": {"title_text_region": 1, "toc_item": 6, "toc_text_region": 6, "active_marker": 1},
        "standard_content": {"title_text_region": 1, "card_panel": 3, "card_text": 3, "source_footer_strip": 1},
        "evidence_overview": {"title_text_region": 1, "evidence_card": 3, "evidence_text_region": 3, "key_claim_text_region": 1},
        "card_grid": {"title_text_region": 1, "grid_card": 6, "grid_card_text_region": 6},
        "methodology_framework": {"title_text_region": 1, "framework_stage": 4, "framework_text_region": 4, "connector_line": 3},
        "process_flow": {"title_text_region": 1, "process_node": 5, "process_text_region": 5, "connector_line": 4},
        "comparison_matrix": {"title_text_region": 1, "comparison_matrix": 1, "source_footer_strip": 1},
        "data_dashboard": {"title_text_region": 1, "kpi_card": 3, "kpi_text": 3, "primary_chart": 1},
        "table_heavy": {"title_text_region": 1, "table_region": 1, "table_header_band": 1, "table_body_grid": 1},
        "timeline_roadmap": {"title_text_region": 1, "timeline_axis": 1, "timeline_phase": 5, "milestone_text_region": 5},
    }[archetype_id]


def _entry(display_name: str, narrative_role: str, required_slots: list[str], *, component_requirements: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "display_name": display_name,
        "narrative_role": narrative_role,
        "required_slots": required_slots,
        "optional_slots": ["source_footer_text"],
        "component_requirements": component_requirements or {},
        "core": narrative_role not in {"image grid with captions", "connected concept nodes", "case narrative", "closing call to action"},
    }


def _base_slots() -> list[dict[str, Any]]:
    return [_slot("background_base", "background_base", (0, 0, 1, 1), "ppt_shape_background", False, False, 0, 0.95)]


def _footer() -> list[dict[str, Any]]:
    return [
        _slot("source_footer_strip", "source_footer_strip", (0.04, 0.91, 0.92, 0.05), "ppt_shape", True, False, 45, 0.92),
        _slot("source_footer_text", "source_footer_text", (0.055, 0.925, 0.60, 0.025), "ppt_text_box", True, False, 46, 0.86),
    ]


def _cover_hero() -> list[dict[str, Any]]:
    return _base_slots() + [
        _slot("hero", "hero_visual_field", (0.54, 0.11, 0.38, 0.68), "replaceable_image_frame", False, True, 12, 0.92),
        _slot("title", "title_text_region", (0.07, 0.20, 0.40, 0.18), "ppt_text_box", True, False, 30, 0.93),
        _slot("subtitle", "subtitle_text_region", (0.075, 0.43, 0.36, 0.10), "ppt_text_box", True, False, 31, 0.90),
        _slot("meta_strip", "meta_text_region", (0.075, 0.60, 0.28, 0.05), "ppt_text_box", True, False, 32, 0.82),
    ] + _footer()


def _section_divider() -> list[dict[str, Any]]:
    return _base_slots() + [
        _slot("section_number", "section_number_text_region", (0.07, 0.18, 0.12, 0.08), "ppt_text_box", True, False, 30, 0.9),
        _slot("section_title", "section_title_text_region", (0.07, 0.31, 0.56, 0.14), "ppt_text_box", True, False, 31, 0.92),
        _slot("section_subtitle", "section_subtitle_text_region", (0.075, 0.50, 0.48, 0.08), "ppt_text_box", True, False, 32, 0.88),
        _slot("progress_indicator", "progress_indicator", (0.07, 0.67, 0.38, 0.025), "ppt_shape", False, False, 20, 0.8),
        _slot("technical_overlay", "technical_overlay", (0.67, 0.14, 0.22, 0.56), "ppt_shape", False, False, 8, 0.78),
    ] + _footer()


def _visual_toc() -> list[dict[str, Any]]:
    slots = _base_slots() + [_slot("title", "title_text_region", (0.07, 0.08, 0.55, 0.10), "ppt_text_box", True, False, 30, 0.92)]
    for i in range(6):
        row, col = divmod(i, 2)
        x, y = 0.07 + col * 0.33, 0.24 + row * 0.17
        slots.append(_slot(f"toc_item_{i+1}", "toc_item", (x, y, 0.28, 0.11), "ppt_shape", True, False, 20, 0.86))
        slots.append(_slot(f"toc_text_{i+1}", "toc_text_region", (x + 0.02, y + 0.03, 0.21, 0.04), "ppt_text_box", True, False, 34, 0.86))
    slots.append(_slot("active_marker", "active_marker", (0.065, 0.235, 0.012, 0.12), "ppt_shape", False, False, 35, 0.82))
    return slots + _footer()


def _standard_content() -> list[dict[str, Any]]:
    slots = _base_slots() + [
        _slot("bg_texture", "decorative_texture", (0.70, 0.04, 0.24, 0.26), "bounded_nonsemantic_raster", False, True, 4, 0.86),
        _slot("hero", "hero_visual_field", (0.63, 0.17, 0.29, 0.55), "replaceable_image_frame", False, True, 12, 0.92),
        _slot("title", "title_text_region", (0.07, 0.10, 0.48, 0.11), "ppt_text_box", True, False, 30, 0.93),
        _slot("subtitle", "subtitle_text_region", (0.075, 0.225, 0.44, 0.07), "ppt_text_box", True, False, 31, 0.90),
        _slot("semantic_icon_1", "semantic_icon", (0.083, 0.645, 0.047, 0.085), "native_vector", True, False, 35, 0.84),
        _slot("technical_overlay", "technical_overlay", (0.05, 0.78, 0.68, 0.06), "ppt_shape", False, False, 8, 0.78),
    ]
    for i, x in enumerate((0.07, 0.255, 0.44), start=1):
        slots.append(_slot(f"card_panel_{i}", "card_panel", (x, 0.36, 0.16, 0.25), "ppt_shape", True, False, 20, 0.90))
        slots.append(_slot(f"card_text_{i}", "body_text_region", (x + 0.015, 0.40, 0.13, 0.14), "ppt_text_box", True, False, 34, 0.88))
    return slots + _footer()


def _evidence_overview() -> list[dict[str, Any]]:
    slots = _base_slots() + [
        _slot("title", "title_text_region", (0.06, 0.08, 0.56, 0.10), "ppt_text_box", True, False, 30, 0.92),
        _slot("key_claim", "key_claim_text_region", (0.07, 0.22, 0.50, 0.10), "ppt_text_box", True, False, 31, 0.88),
    ]
    for i, x in enumerate((0.07, 0.35, 0.63), start=1):
        slots.append(_slot(f"evidence_card_{i}", "evidence_card", (x, 0.42, 0.22, 0.32), "ppt_shape", True, False, 20, 0.86))
        slots.append(_slot(f"evidence_text_{i}", "evidence_text_region", (x + 0.02, 0.47, 0.17, 0.16), "ppt_text_box", True, False, 34, 0.86))
        slots.append(_slot(f"evidence_tag_{i}", "evidence_tag_chip", (x + 0.02, 0.66, 0.10, 0.04), "ppt_shape", True, False, 22, 0.80))
    return slots + _footer()


def _card_grid() -> list[dict[str, Any]]:
    slots = _base_slots() + [_slot("title", "title_text_region", (0.06, 0.08, 0.56, 0.10), "ppt_text_box", True, False, 30, 0.92)]
    for i in range(6):
        row, col = divmod(i, 3)
        x, y = 0.07 + col * 0.29, 0.26 + row * 0.25
        slots.append(_slot(f"grid_card_{i+1}", "grid_card", (x, y, 0.23, 0.19), "ppt_shape", True, False, 20, 0.86))
        slots.append(_slot(f"grid_card_text_{i+1}", "grid_card_text_region", (x + 0.018, y + 0.04, 0.17, 0.08), "ppt_text_box", True, False, 34, 0.84))
    return slots + _footer()


def _methodology_framework() -> list[dict[str, Any]]:
    slots = _base_slots() + [_slot("title", "title_text_region", (0.06, 0.08, 0.56, 0.10), "ppt_text_box", True, False, 30, 0.92)]
    for i, x in enumerate((0.08, 0.30, 0.52, 0.74), start=1):
        slots.append(_slot(f"framework_stage_{i}", "framework_stage", (x, 0.34, 0.15, 0.26), "ppt_shape", True, False, 20, 0.86))
        slots.append(_slot(f"framework_text_{i}", "framework_text_region", (x + 0.015, 0.40, 0.11, 0.11), "ppt_text_box", True, False, 34, 0.84))
        if i < 4:
            slots.append(_slot(f"connector_line_{i}", "connector_line", (x + 0.16, 0.46, 0.07, 0.02), "ppt_connector", False, False, 25, 0.80))
    return slots + _footer()


def _process_flow() -> list[dict[str, Any]]:
    slots = _base_slots() + [_slot("title", "title_text_region", (0.06, 0.08, 0.56, 0.10), "ppt_text_box", True, False, 30, 0.92), _slot("phase_rail", "phase_rail", (0.08, 0.28, 0.76, 0.03), "ppt_shape", False, False, 18, 0.8)]
    for i, x in enumerate((0.08, 0.25, 0.42, 0.59, 0.76), start=1):
        slots.append(_slot(f"process_node_{i}", "process_node", (x, 0.38, 0.11, 0.17), "ppt_shape", True, False, 20, 0.86))
        slots.append(_slot(f"process_text_{i}", "process_text_region", (x + 0.012, 0.43, 0.08, 0.06), "ppt_text_box", True, False, 34, 0.84))
        if i < 5:
            slots.append(_slot(f"connector_line_{i}", "connector_line", (x + 0.12, 0.46, 0.05, 0.02), "ppt_connector", False, False, 25, 0.80))
    return slots + _footer()


def _comparison_matrix() -> list[dict[str, Any]]:
    return _base_slots() + [
        _slot("title", "title_text_region", (0.06, 0.08, 0.56, 0.10), "ppt_text_box", True, False, 30, 0.92),
        _slot("comparison_matrix", "comparison_matrix", (0.07, 0.27, 0.72, 0.52), "native_table", True, False, 26, 0.90),
        _slot("matrix_header_band", "matrix_header_band", (0.07, 0.27, 0.72, 0.08), "ppt_shape", True, False, 27, 0.88),
    ] + _footer()


def _data_dashboard() -> list[dict[str, Any]]:
    slots = _base_slots() + [
        _slot("title", "title_text_region", (0.06, 0.08, 0.56, 0.10), "ppt_text_box", True, False, 30, 0.93),
        _slot("subtitle", "subtitle_text_region", (0.065, 0.19, 0.46, 0.05), "ppt_text_box", True, False, 31, 0.88),
        _slot("primary_chart", "primary_chart", (0.06, 0.52, 0.52, 0.31), "native_chart", True, False, 28, 0.90),
        _slot("insight_panel", "insight_panel", (0.64, 0.22, 0.28, 0.46), "ppt_shape", True, False, 22, 0.86),
        _slot("insight_text", "insight_text_region", (0.665, 0.27, 0.23, 0.27), "ppt_text_box", True, False, 35, 0.84),
    ]
    for i, x in enumerate((0.06, 0.245, 0.43), start=1):
        slots.append(_slot(f"kpi_card_{i}", "kpi_card", (x, 0.30, 0.16, 0.16), "ppt_shape", True, False, 18, 0.88))
        slots.append(_slot(f"kpi_text_{i}", "kpi_text_region", (x + 0.015, 0.325, 0.13, 0.08), "ppt_text_box", True, False, 34, 0.88))
    return slots + _footer()


def _table_heavy() -> list[dict[str, Any]]:
    return _base_slots() + [
        _slot("title", "title_text_region", (0.06, 0.08, 0.56, 0.10), "ppt_text_box", True, False, 30, 0.93),
        _slot("subtitle", "subtitle_text_region", (0.065, 0.19, 0.46, 0.05), "ppt_text_box", True, False, 31, 0.88),
        _slot("table_region", "table_region", (0.06, 0.30, 0.70, 0.50), "native_table", True, False, 26, 0.91),
        _slot("table_header_band", "table_header_band", (0.06, 0.30, 0.70, 0.07), "ppt_shape", True, False, 27, 0.88),
        _slot("table_body_grid", "table_body_grid", (0.06, 0.37, 0.70, 0.43), "ppt_shape", True, False, 28, 0.88),
        _slot("kpi_chip_1", "kpi_chip", (0.80, 0.33, 0.12, 0.06), "ppt_shape", True, False, 20, 0.80),
    ] + _footer()


def _timeline_roadmap() -> list[dict[str, Any]]:
    slots = _base_slots() + [_slot("title", "title_text_region", (0.06, 0.08, 0.56, 0.10), "ppt_text_box", True, False, 30, 0.92), _slot("timeline_axis", "timeline_axis", (0.08, 0.48, 0.78, 0.03), "ppt_connector", False, False, 20, 0.88)]
    for i, x in enumerate((0.08, 0.25, 0.42, 0.59, 0.76), start=1):
        slots.append(_slot(f"timeline_phase_{i}", "timeline_phase", (x, 0.36 if i % 2 else 0.55, 0.12, 0.12), "ppt_shape", True, False, 22, 0.86))
        slots.append(_slot(f"milestone_text_{i}", "milestone_text_region", (x + 0.01, (0.39 if i % 2 else 0.58), 0.09, 0.04), "ppt_text_box", True, False, 34, 0.84))
    return slots + _footer()


def _photo_caption_grid() -> list[dict[str, Any]]:
    return _card_grid()


def _concept_map() -> list[dict[str, Any]]:
    return _process_flow()


def _case_study() -> list[dict[str, Any]]:
    return _evidence_overview()


def _closing() -> list[dict[str, Any]]:
    return _cover_hero()


def _slot(slot_id: str, role: str, bbox: tuple[float, float, float, float], target: str, semantic_allowed: bool, raster_allowed: bool, z_order: int, confidence: float) -> dict[str, Any]:
    return {
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


_SLOT_BUILDERS = {
    "cover_hero": _cover_hero,
    "section_divider": _section_divider,
    "visual_toc": _visual_toc,
    "standard_content": _standard_content,
    "evidence_overview": _evidence_overview,
    "card_grid": _card_grid,
    "methodology_framework": _methodology_framework,
    "process_flow": _process_flow,
    "comparison_matrix": _comparison_matrix,
    "data_dashboard": _data_dashboard,
    "table_heavy": _table_heavy,
    "timeline_roadmap": _timeline_roadmap,
    "photo_caption_grid": _photo_caption_grid,
    "concept_map": _concept_map,
    "case_study": _case_study,
    "closing": _closing,
}
