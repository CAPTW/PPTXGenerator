"""Reusable E03 editable component library."""

from __future__ import annotations

from typing import Any


REQUIRED_COMPONENTS = (
    "title_block",
    "subtitle_block",
    "source_footer",
    "card_panel",
    "KPI_card",
    "evidence_card",
    "SVG_icon_slot",
    "native_chart_placeholder",
    "editable_shape_chart",
    "native_table",
    "editable_shape_grid_table",
    "process_node",
    "connector_line",
    "timeline_phase",
    "image_frame",
    "hero_visual_field",
    "decorative_texture",
    "technical_overlay",
)


def build_component_library() -> dict[str, Any]:
    return {
        "schema_name": "e03_component_library",
        "components": {component_id: _component(component_id) for component_id in REQUIRED_COMPONENTS},
        "canva_parity_claimed": False,
    }


def validate_component_library(library: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(set(REQUIRED_COMPONENTS) - set(library.get("components", {})))
    failures = []
    for component_id, component in library.get("components", {}).items():
        for field in ("pptx_primitive_target", "editability_policy", "raster_policy", "min_content_capacity", "overflow_policy", "allowed_fallback", "forbidden_fallback"):
            if field not in component:
                failures.append(f"{component_id}_missing_{field}")
        if component.get("editability_policy") == "rasterized":
            failures.append(f"{component_id}_rasterized")
    return {"schema_name": "e03_component_library_validation", "status": "passed" if not missing and not failures else "failed", "missing": missing, "failures": failures, "canva_parity_claimed": False}


def build_component_coverage_matrix(library: dict[str, Any]) -> dict[str, Any]:
    coverage = {
        "cover_hero": {"title_block": True, "subtitle_block": True, "hero_visual_field": True, "source_footer": True},
        "section_divider": {"title_block": True, "connector_line": True, "technical_overlay": True},
        "visual_toc": {"title_block": True, "card_panel": True, "source_footer": True},
        "standard_content": {"title_block": True, "card_panel": True, "SVG_icon_slot": True, "hero_visual_field": True},
        "evidence_overview": {"title_block": True, "evidence_card": True, "source_footer": True},
        "card_grid": {"title_block": True, "card_panel": True},
        "methodology_framework": {"title_block": True, "process_node": True, "connector_line": True},
        "process_flow": {"title_block": True, "process_node": True, "connector_line": True},
        "comparison_matrix": {"title_block": True, "editable_shape_grid_table": True, "native_table": True},
        "data_dashboard": {"title_block": True, "KPI_card": True, "native_chart_placeholder": True},
        "table_heavy": {"title_block": True, "native_table": True, "editable_shape_grid_table": True},
        "timeline_roadmap": {"title_block": True, "timeline_phase": True, "connector_line": True},
    }
    all_known = all(component_id in library.get("components", {}) for row in coverage.values() for component_id, present in row.items() if present)
    return {"schema_name": "component_coverage_matrix", "status": "passed" if all_known else "failed", "coverage": coverage, "canva_parity_claimed": False}


def _component(component_id: str) -> dict[str, Any]:
    primitive = {
        "native_chart_placeholder": "native_chart",
        "editable_shape_chart": "editable_shape_chart",
        "native_table": "native_table",
        "editable_shape_grid_table": "editable_shape_grid_table",
        "SVG_icon_slot": "native_vector",
        "image_frame": "replaceable_image_frame",
        "hero_visual_field": "replaceable_image_frame",
        "connector_line": "ppt_connector",
    }.get(component_id, "ppt_shape" if "card" in component_id or "node" in component_id or "phase" in component_id or component_id in {"source_footer", "technical_overlay", "decorative_texture"} else "ppt_text_box")
    return {
        "component_id": component_id,
        "pptx_primitive_target": primitive,
        "editability_policy": "editable_or_replaceable",
        "raster_policy": "bounded_nonsemantic_only" if primitive == "replaceable_image_frame" else "semantic_raster_forbidden",
        "min_content_capacity": 24 if "title" not in component_id else 50,
        "overflow_policy": "shrink_within_slot_or_request_layout_change",
        "allowed_fallback": "editable_shape_fallback",
        "forbidden_fallback": ["full_slide_raster", "screenshot_slide", "semantic_raster"],
    }
