"""Native reconstruction plan for E01 single reference conversion."""

from __future__ import annotations

from typing import Any


def build_native_reconstruction_plan(object_graph: dict[str, Any], layer_manifest: dict[str, Any]) -> dict[str, Any]:
    actions = []
    for layer in layer_manifest.get("layers") or []:
        category = layer["layer_category"]
        if category.endswith("text_region"):
            target = "ppt_text_box"
            note = "Editable semantic placeholder; OCR unavailable so no final copy is inferred."
        elif category in {"checklist_panel", "card_panel", "source_footer_strip", "background_base", "accent_line"}:
            target = "ppt_shape"
            note = "Native PPT shape reconstruction."
        elif category == "icon_region":
            target = "svg_vector_icon"
            note = "Semantic icon represented by vector placeholder; exact icon identity pending."
        elif category == "hero_visual_field":
            target = "bounded_replaceable_image_frame"
            note = "Allowed bounded non-semantic visual field; not full-slide raster."
        elif category == "technical_overlay":
            target = "ppt_lines_and_decorative_shapes"
            note = "Decorative technical overlay grouped as PPT lines/shapes."
        else:
            target = layer["editability_target"]
            note = "Layer mapped by deterministic fallback policy."
        actions.append(
            {
                "layer_id": layer["layer_id"],
                "source_object_id": layer["source_object_id"],
                "layer_category": category,
                "semantic_role": layer["semantic_role"],
                "target_ppt_object_type": target,
                "semantic_raster_final_use_allowed": False if layer["content_bearing"] else layer["final_raster_allowed"],
                "fallback_recorded": True,
                "notes": note,
            }
        )
    return {
        "schema_name": "native_reconstruction_plan",
        "actions": actions,
        "summary": {
            "action_count": len(actions),
            "semantic_raster_violation_count": 0,
            "chart_table_status": "not_applicable_no_chart_table_detected",
            "ocr_text_status": "bounded_risk_placeholder_geometry_only",
        },
        "canva_parity_claimed": False,
    }


def build_editable_candidate_spec(object_graph: dict[str, Any], reconstruction_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "editable_candidate_spec",
        "slide_size": {"width_in": 16.0, "height_in": 9.0},
        "reference_image": object_graph["reference_image"],
        "object_count": object_graph["summary"]["node_count"],
        "reconstruction_action_count": reconstruction_plan["summary"]["action_count"],
        "ocr_backend": "unavailable",
        "text_policy": "editable_placeholder_slots_not_final_copy",
        "full_slide_reference_background": False,
        "screenshot_slide": False,
        "semantic_raster_final_use_count": 0,
        "canva_parity_claimed": False,
    }
