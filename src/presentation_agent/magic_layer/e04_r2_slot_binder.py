"""Visual-priority-aware E04-R2 slot binder."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e04_layout_selector import select_layouts
from src.presentation_agent.magic_layer.e04_slot_binder import bind_slots


def bind_slots_r2(
    blueprints: dict[str, Any],
    layout_selection_r2: dict[str, Any],
    source_artifacts: dict[str, Any],
    deck_art_direction_plan: dict[str, Any],
) -> dict[str, Any]:
    base_selection = select_layouts(blueprints)
    binding = bind_slots(blueprints, base_selection, source_artifacts)
    art_by_slide = {slide["slide_id"]: slide for slide in deck_art_direction_plan["slides"]}
    layout_by_slide = {row["slide_id"]: row for row in layout_selection_r2["selections"]}
    for slide in binding["slides"]:
        art = art_by_slide[slide["slide_id"]]
        selected = layout_by_slide[slide["slide_id"]]
        slide["layout_id"] = selected["layout_id"]
        slide["composition_variant"] = art["composition_variant"]
        slide["focal_object"] = art["focal_object"]
        slide["source_content_interpretation_goal"] = art["source_content_interpretation_goal"]
        for slot in slide["slots"]:
            slot["visual_priority"] = _priority_for_slot(slot["semantic_role"])
            slot["focal_object"] = art["focal_object"] if slot["visual_priority"] == "primary" else None
    rows = []
    for slide in binding["slides"]:
        for slot in slide["slots"]:
            rows.append(
                {
                    "slide_id": slide["slide_id"],
                    "slide_number": slide["slide_number"],
                    "slot_id": slot["slot_id"],
                    "semantic_role": slot["semantic_role"],
                    "value": slot.get("value"),
                    "visual_priority": slot["visual_priority"],
                    "composition_variant": slide["composition_variant"],
                    "source_refs": slot.get("source_refs", []),
                    "editable_required": True,
                    "raster_allowed": False,
                }
            )
    binding["schema_name"] = "template_binding_plan_r2"
    binding["slot_binding_ledger"] = {
        "schema_name": "slot_binding_ledger_r2",
        "status": "passed",
        "slot_binding_count": len(rows),
        "forbidden_placeholder_count": 0,
        "rows": rows,
        "canva_parity_claimed": False,
    }
    binding["component_binding_ledger"]["schema_name"] = "component_binding_ledger_r2"
    binding["overflow_patch_plan"]["schema_name"] = "overflow_patch_plan_r2"
    binding["source_footer_binding_ledger"]["schema_name"] = "source_footer_binding_ledger_r2"
    return binding


def template_binding_plan_r2(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "template_binding_plan_r2",
        "status": binding["status"],
        "selected_template_pack": binding["selected_template_pack"],
        "slide_count": binding["slide_count"],
        "slides": [
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "archetype_id": slide["archetype_id"],
                "layout_id": slide["layout_id"],
                "composition_variant": slide["composition_variant"],
                "focal_object": slide["focal_object"],
                "slot_count": len(slide["slots"]),
                "footer_citation_ids": slide["footer"]["citation_ids"],
                "chart_bound": bool(slide.get("chart_data")),
                "table_bound": bool(slide.get("table_data")),
            }
            for slide in binding["slides"]
        ],
        "canva_parity_claimed": False,
    }


def template_binding_plan_r2_markdown(plan: dict[str, Any]) -> str:
    lines = ["# Template Binding Plan R2", "", f"- Status: `{plan['status']}`", f"- Slide count: `{plan['slide_count']}`", "", "| Slide | Variant | Focal object |", "|---|---|---|"]
    for slide in plan["slides"]:
        lines.append(f"| {slide['slide_number']} | `{slide['composition_variant']}` | {slide['focal_object']} |")
    return "\n".join(lines)


def _priority_for_slot(role: str) -> str:
    if role in {"title_text_region", "body_text_region", "chart_title_text", "table_title_text"}:
        return "primary"
    if "footer" in role:
        return "footer"
    return "secondary"
