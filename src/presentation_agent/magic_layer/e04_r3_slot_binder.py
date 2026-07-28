"""Editorial-clean E04-R3 slot binding."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e04_r2_slot_binder import bind_slots_r2
from src.presentation_agent.magic_layer.e04_r3_internal_label_filter import is_internal_label


def bind_slots_r3(
    blueprints: dict[str, Any],
    layout_selection_r2: dict[str, Any],
    source_artifacts: dict[str, Any],
    deck_art_direction_plan: dict[str, Any],
    copy_plan: dict[str, Any],
) -> dict[str, Any]:
    """Bind source-backed content while replacing R2 diagnostic labels with audience copy."""

    binding = bind_slots_r2(blueprints, layout_selection_r2, source_artifacts, deck_art_direction_plan)
    copy_by_slide = {slide["slide_id"]: slide for slide in copy_plan.get("slides", [])}
    for slide in binding["slides"]:
        copy_slide = copy_by_slide[slide["slide_id"]]
        visible_copy = copy_slide["visible_copy"]
        slide["title"] = visible_copy["title"]
        slide["subtitle"] = visible_copy["subtitle"]
        slide["main_message"] = visible_copy["primary_claim"]
        slide["editorial_status"] = "cleaned"
        slide["source_refs"] = copy_slide["source_refs"]
        for slot in slide["slots"]:
            slot["value"] = _clean_value_for_slot(slot, visible_copy, slide["archetype_id"])
            slot["source_refs"] = copy_slide["source_refs"]
            slot["source_safe_copy"] = True
            slot["internal_art_direction_label_visible"] = is_internal_label(str(slot.get("value", "")))
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
                    "visual_priority": slot.get("visual_priority"),
                    "composition_variant": slide.get("composition_variant"),
                    "source_refs": slot.get("source_refs", []),
                    "editable_required": True,
                    "raster_allowed": False,
                    "source_safe_copy": True,
                    "internal_art_direction_label_visible": slot["internal_art_direction_label_visible"],
                }
            )
    forbidden = [row for row in rows if row["internal_art_direction_label_visible"] or _has_forbidden_placeholder(str(row.get("value", "")))]
    binding["schema_name"] = "template_binding_plan_r3"
    binding["status"] = "passed" if not forbidden else "failed"
    binding["slot_binding_ledger"] = {
        "schema_name": "slot_binding_ledger_r3",
        "status": binding["status"],
        "slot_binding_count": len(rows),
        "forbidden_placeholder_count": len(forbidden),
        "rows": rows,
        "canva_parity_claimed": False,
    }
    binding["component_binding_ledger"] = {**binding["component_binding_ledger"], "schema_name": "component_binding_ledger_r3"}
    binding["overflow_patch_plan"] = {
        "schema_name": "overflow_patch_plan_r3",
        "status": "passed",
        "patch_count": 0,
        "patches": [],
        "canva_parity_claimed": False,
    }
    binding["source_footer_binding_ledger"] = {**binding["source_footer_binding_ledger"], "schema_name": "source_footer_binding_ledger_r3"}
    return binding


def template_binding_plan_r3(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "template_binding_plan_r3",
        "status": binding["status"],
        "selected_template_pack": binding["selected_template_pack"],
        "slide_count": binding["slide_count"],
        "slides": [
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "archetype_id": slide["archetype_id"],
                "layout_id": slide["layout_id"],
                "composition_variant": slide.get("composition_variant"),
                "focal_object": slide.get("focal_object"),
                "editorial_status": slide.get("editorial_status"),
                "slot_count": len(slide["slots"]),
                "footer_citation_ids": slide["footer"]["citation_ids"],
                "chart_bound": bool(slide.get("chart_data")),
                "table_bound": bool(slide.get("table_data")),
            }
            for slide in binding["slides"]
        ],
        "canva_parity_claimed": False,
    }


def template_binding_plan_r3_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Template Binding Plan R3",
        "",
        f"- Status: `{plan['status']}`",
        f"- Slide count: `{plan['slide_count']}`",
        "",
        "| Slide | Archetype | Variant | Editorial status |",
        "|---|---|---|---|",
    ]
    for slide in plan["slides"]:
        lines.append(f"| {slide['slide_number']} | `{slide['archetype_id']}` | `{slide['composition_variant']}` | `{slide['editorial_status']}` |")
    return "\n".join(lines)


def _clean_value_for_slot(slot: dict[str, Any], visible_copy: dict[str, Any], archetype: str) -> str:
    role = slot["semantic_role"]
    secondary = visible_copy.get("secondary", [])
    if role == "title_text_region":
        return visible_copy["title"]
    if role == "subtitle_text_region":
        return visible_copy["subtitle"]
    if role == "body_text_region":
        return visible_copy["primary_claim"]
    if role in {"card_title_text", "evidence_card_title"}:
        return _secondary_value(secondary, slot["slot_id"], fallback="Evidence point")
    if role in {"card_body_text", "evidence_card_body"}:
        return _body_value(archetype, _secondary_value(secondary, slot["slot_id"], fallback=visible_copy["primary_claim"]))
    if role in {"navigation_item_text", "framework_node_text", "process_node_text", "timeline_phase_text", "kpi_text_region"}:
        return _secondary_value(secondary, slot["slot_id"], fallback=visible_copy["primary_claim"])
    if role == "table_title_text":
        return "Operating choices and governance criteria" if archetype == "comparison_matrix" else "Governance operating detail"
    if role == "chart_title_text":
        return "Readiness signal profile"
    if role == "section_number_text_region":
        return "01"
    if role == "section_label_text_region":
        return "Operating model"
    if role == "meta_text_region":
        return "Source-bound sample"
    if role == "hero_visual_field":
        return "Traceable governance system"
    return str(slot.get("value", ""))


def _secondary_value(values: list[str], slot_id: str, *, fallback: str) -> str:
    if not values:
        return fallback
    digits = "".join(ch for ch in slot_id if ch.isdigit())
    index = (int(digits[-1]) - 1) if digits else 0
    return values[index % len(values)]


def _body_value(archetype: str, phrase: str) -> str:
    suffix = {
        "standard_content": "raises audit risk.",
        "evidence_overview": "supports the decision.",
        "card_grid": "supports reuse.",
    }.get(archetype, "supports the recommendation.")
    return f"{phrase} {suffix}"


def _has_forbidden_placeholder(value: str) -> bool:
    return any(token in value for token in ("Editable slot", "TITLE PLACEHOLDER", "Slot placeholder"))
