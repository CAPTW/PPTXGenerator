"""Reference registry for the E02H 4-core hybrid Canva+ gate."""

from __future__ import annotations

from typing import Any


REFERENCE_IDS = [
    "maritime_checklist_hero",
    "process_workflow_infographic",
    "data_dashboard_hybrid",
    "table_matrix_hybrid",
]


def build_e02h_reference_registry() -> dict[str, dict[str, Any]]:
    return {
        "maritime_checklist_hero": {
            "reference_id": "maritime_checklist_hero",
            "display_name": "Maritime Checklist Hero",
            "source_policy": "e01h_p_regression_fixture_rebuilt",
            "reference_generation": "reuse_e01h_reference_rebuild_candidate",
            "component_requirements": {
                "semantic_text": "ppt_text_box",
                "semantic_icons": "native_vector",
                "checklist_micro_components": "native_shape_text_vector",
                "hero_visual_field": "replaceable_image_frame",
            },
            "full_slide_reference_background_allowed": False,
            "screenshot_slide_allowed": False,
            "semantic_raster_allowed": False,
        },
        "process_workflow_infographic": {
            "reference_id": "process_workflow_infographic",
            "display_name": "Process Workflow Infographic",
            "source_policy": "local_generated_reference",
            "reference_generation": "deterministic_local_pil_reference",
            "component_requirements": {
                "title_text": "ppt_text_box",
                "process_node_text": "ppt_text_box",
                "process_nodes": "ppt_shape",
                "connectors": "ppt_vector",
                "semantic_icons": "native_vector",
                "footer_source": "ppt_text_box",
            },
            "full_slide_reference_background_allowed": False,
            "screenshot_slide_allowed": False,
            "semantic_raster_allowed": False,
        },
        "data_dashboard_hybrid": {
            "reference_id": "data_dashboard_hybrid",
            "display_name": "Data Dashboard Hybrid",
            "source_policy": "local_generated_reference",
            "reference_generation": "deterministic_local_pil_reference",
            "component_requirements": {
                "title_text": "ppt_text_box",
                "kpi_card_text": "ppt_text_box",
                "kpi_cards": "ppt_shape",
                "primary_chart": "native_chart",
                "insight_text": "ppt_text_box",
                "footer_source": "ppt_text_box",
            },
            "full_slide_reference_background_allowed": False,
            "screenshot_slide_allowed": False,
            "semantic_raster_allowed": False,
        },
        "table_matrix_hybrid": {
            "reference_id": "table_matrix_hybrid",
            "display_name": "Table Matrix Hybrid",
            "source_policy": "local_generated_reference",
            "reference_generation": "deterministic_local_pil_reference",
            "component_requirements": {
                "title_text": "ppt_text_box",
                "table_matrix": "native_table",
                "header_band": "ppt_shape",
                "table_text": "ppt_text_box_or_native_table_text",
                "footer_source": "ppt_text_box",
            },
            "full_slide_reference_background_allowed": False,
            "screenshot_slide_allowed": False,
            "semantic_raster_allowed": False,
        },
    }
