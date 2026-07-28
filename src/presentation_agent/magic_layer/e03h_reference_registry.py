"""Registry for the E03H 12-core hybrid Canva+ reference pack."""

from __future__ import annotations

from typing import Any


CORE_REFERENCE_IDS = [
    "maritime_checklist_hero",
    "process_workflow_infographic",
    "data_dashboard_hybrid",
    "table_matrix_hybrid",
    "cover_hero_photo_editorial",
    "standard_content_card_cluster",
    "evidence_stack_visual",
    "comparison_matrix_hybrid",
    "methodology_framework_layered",
    "timeline_roadmap_hybrid",
    "visual_toc_navigation",
    "photo_caption_grid_hybrid",
]

OPTIONAL_REFERENCE_IDS = [
    "case_study_storyboard",
    "concept_map_network",
    "section_divider_premium",
    "closing_recommendation_panel",
]


def build_e03h_reference_pack_registry(include_optional: bool = False) -> dict[str, dict[str, Any]]:
    ids = [*CORE_REFERENCE_IDS, *(OPTIONAL_REFERENCE_IDS if include_optional else [])]
    registry = {}
    for reference_id in ids:
        registry[reference_id] = _entry(reference_id)
    return registry


def hybrid_reference_pack_registry_markdown(registry: dict[str, dict[str, Any]]) -> str:
    lines = ["# Hybrid Reference Pack Registry", "", f"- Reference count: `{len(registry)}`", "- Broad Canva parity claimed: `False`", ""]
    for reference_id, row in registry.items():
        lines.append(f"## {reference_id}")
        lines.append(f"- Category: `{row['category']}`")
        lines.append(f"- Visual role: `{row['visual_role']}`")
        lines.append(f"- Reference source: `{row['reference_source']}`")
    return "\n".join(lines)


def _entry(reference_id: str) -> dict[str, Any]:
    category = _category(reference_id)
    return {
        "reference_id": reference_id,
        "category": category,
        "visual_role": _visual_role(reference_id),
        "required_semantic_slots": _semantic_slots(reference_id),
        "required_visual_backplates": ["background_substrate", "bounded_texture_or_visual_field"],
        "required_native_components": _native_components(reference_id),
        "icon_policy": "semantic_icons_native_vector_when_present",
        "chart_policy": "native_chart_required" if reference_id == "data_dashboard_hybrid" else "not_applicable",
        "table_policy": "native_table_required" if reference_id in {"table_matrix_hybrid", "comparison_matrix_hybrid"} else "not_applicable",
        "footer_policy": "editable_source_footer_required",
        "allowed_raster_policy": {"bounded_nonsemantic_backplates": True, "replaceable_visual_fields": True},
        "forbidden_raster_policy": {
            "full_slide_reference_background": True,
            "screenshot_slide": True,
            "semantic_text": True,
            "semantic_icons": True,
            "charts_tables": True,
            "cards_footer": True,
        },
        "expected_visual_density": "high",
        "expected_micro_components": _micro_components(reference_id),
        "reference_source": "e02h_regression" if reference_id in CORE_REFERENCE_IDS[:4] else "local_generated",
        "core": reference_id in CORE_REFERENCE_IDS,
        "canva_parity_claimed": False,
    }


def _category(reference_id: str) -> str:
    if reference_id in {"data_dashboard_hybrid"}:
        return "dashboard"
    if reference_id in {"table_matrix_hybrid", "comparison_matrix_hybrid"}:
        return "matrix_table"
    if reference_id in {"process_workflow_infographic", "methodology_framework_layered", "timeline_roadmap_hybrid"}:
        return "process_timeline"
    if reference_id in {"cover_hero_photo_editorial", "photo_caption_grid_hybrid"}:
        return "visual_photo"
    return "content_system"


def _visual_role(reference_id: str) -> str:
    return {
        "cover_hero_photo_editorial": "hero image plus editorial title hierarchy",
        "standard_content_card_cluster": "three-card semantic content cluster",
        "evidence_stack_visual": "claim evidence source hierarchy",
        "comparison_matrix_hybrid": "native comparison matrix",
        "methodology_framework_layered": "layered framework with connectors",
        "timeline_roadmap_hybrid": "milestone rail and sequence",
        "visual_toc_navigation": "navigation item system",
        "photo_caption_grid_hybrid": "replaceable photo frames with editable captions",
    }.get(reference_id, reference_id.replace("_", " "))


def _semantic_slots(reference_id: str) -> list[str]:
    base = ["title_text", "footer_source_text"]
    if reference_id == "data_dashboard_hybrid":
        return [*base, "kpi_card_text", "primary_chart", "insight_text"]
    if reference_id in {"table_matrix_hybrid", "comparison_matrix_hybrid"}:
        return [*base, "table_matrix", "table_header_band"]
    if reference_id in {"process_workflow_infographic", "methodology_framework_layered"}:
        return [*base, "process_node_text", "process_connector", "semantic_icon"]
    if reference_id == "timeline_roadmap_hybrid":
        return [*base, "milestone_text", "timeline_connector"]
    if reference_id == "photo_caption_grid_hybrid":
        return [*base, "thumbnail_caption_text", "replaceable_image_frame"]
    return [*base, "body_text", "semantic_icon"]


def _native_components(reference_id: str) -> dict[str, str]:
    components = {"text": "ppt_text_box", "footer": "ppt_text_box", "semantic_icons": "native_vector"}
    if reference_id == "data_dashboard_hybrid":
        components["primary_chart"] = "native_chart"
    if reference_id in {"table_matrix_hybrid", "comparison_matrix_hybrid"}:
        components["table_matrix"] = "native_table"
    if reference_id in {"process_workflow_infographic", "methodology_framework_layered", "timeline_roadmap_hybrid"}:
        components["connectors"] = "ppt_vector"
    return components


def _micro_components(reference_id: str) -> list[str]:
    if reference_id in {"table_matrix_hybrid", "comparison_matrix_hybrid"}:
        return ["header_band", "grid_rules", "cell_text", "source_footer"]
    if reference_id == "data_dashboard_hybrid":
        return ["kpi_cards", "chart_axes", "insight_panel", "source_footer"]
    if reference_id in {"process_workflow_infographic", "methodology_framework_layered", "timeline_roadmap_hybrid"}:
        return ["node_shapes", "connector_lines", "step_icons", "source_footer"]
    return ["semantic_text", "semantic_icon_or_marker", "bounded_backplate", "source_footer"]
