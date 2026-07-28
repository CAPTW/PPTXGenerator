"""Build the E06.1 16-slide layout contract from PPTX coordinates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_layout_contract_16_slides(
    extraction: dict[str, Any],
    *,
    icon_size_policy: dict[str, Any],
    source_deck_path: str,
) -> dict[str, Any]:
    slides: list[dict[str, Any]] = []
    for source_slide in extraction.get("slides", []):
        objects = [dict(obj) for obj in source_slide.get("objects", [])]
        _attach_icon_contract_metadata(objects, icon_size_policy)
        semantic_icons = [obj for obj in objects if obj.get("object_type") == "semantic_icon"]
        text_zones = [obj for obj in objects if obj.get("object_type") in {"text", "source_footer"} and obj.get("content_bearing")]
        source_regions = [obj for obj in objects if obj.get("object_type") == "source_footer"]
        table_regions = [obj for obj in objects if obj.get("object_type") == "table_region"]
        chart_regions = [obj for obj in objects if obj.get("object_type") == "chart_region"]
        card_regions = [obj for obj in objects if obj.get("object_type") == "card_region"]
        slides.append(
            {
                "slide_id": source_slide["slide_id"],
                "slide_number": source_slide["slide_number"],
                "archetype_id": source_slide["archetype_id"],
                "slide_size": extraction["slide_size"],
                "objects": objects,
                "semantic_icon_slots": [_icon_slot(obj) for obj in semantic_icons],
                "text_zones": [_zone(obj) for obj in text_zones],
                "source_footer_regions": [_zone(obj) for obj in source_regions],
                "table_chart_card_regions": {
                    "table_regions": [_zone(obj) for obj in table_regions],
                    "chart_regions": [_zone(obj) for obj in chart_regions],
                    "card_regions": [_zone(obj) for obj in card_regions],
                },
                "z_order": [{"object_id": obj["object_id"], "name": obj["name"], "z_order": obj["z_order"]} for obj in objects],
            }
        )
    object_count = sum(len(slide["objects"]) for slide in slides)
    semantic_icon_count = sum(len(slide["semantic_icon_slots"]) for slide in slides)
    return {
        "schema_name": "layout_contract_16_slides",
        "contract_version": "v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_of_truth": "JSON layout contract; built from E06 baseline PPTX coordinates for the initial precision baseline",
        "source_deck_path": source_deck_path,
        "slide_size": extraction.get("slide_size", {}),
        "coordinate_spaces": ["normalized", "inches", "emu"],
        "slides": slides,
        "summary": {
            "slide_count": len(slides),
            "object_count": object_count,
            "semantic_icon_count": semantic_icon_count,
            "source_footer_region_count": sum(len(slide["source_footer_regions"]) for slide in slides),
            "text_zone_count": sum(len(slide["text_zones"]) for slide in slides),
        },
        "broad_canva_parity_claimed": False,
    }


def _attach_icon_contract_metadata(objects: list[dict[str, Any]], icon_size_policy: dict[str, Any]) -> None:
    by_name = {obj["name"]: obj for obj in objects}
    slot_to_token = icon_size_policy.get("slot_type_to_token", {})
    for obj in objects:
        if obj.get("object_type") != "semantic_icon":
            continue
        icon = obj.get("icon_metadata", {})
        slot_type = icon.get("slot_type")
        component_id = icon.get("component_id")
        bg_name = obj["name"].replace("icon::", "icon_bg::", 1)
        anchor = by_name.get(bg_name) or _nearest_component(objects, component_id, obj)
        obj["slot_type"] = slot_type
        obj["size_token"] = slot_to_token.get(slot_type, "icon_card_small")
        obj["anchor_component_id"] = component_id
        obj["anchor_object_id"] = anchor.get("object_id") if anchor else None
        obj["anchor_bbox_norm"] = anchor.get("bbox_norm") if anchor else None
        obj["anchor_position"] = _anchor_position(slot_type)
        obj["constraints"] = {
            **obj.get("constraints", {}),
            "slot_type": slot_type,
            "size_token": obj["size_token"],
            "anchor_component_id": component_id,
            "anchor_object_id": obj["anchor_object_id"],
        }


def _nearest_component(objects: list[dict[str, Any]], component_id: str | None, icon: dict[str, Any]) -> dict[str, Any] | None:
    if not component_id:
        return None
    needle = component_id.lower()
    candidates = [obj for obj in objects if needle in obj.get("name", "").lower() and obj.get("object_id") != icon.get("object_id")]
    if candidates:
        return min(candidates, key=lambda obj: _center_distance(obj.get("bbox_norm", {}), icon.get("bbox_norm", {})))
    return None


def _center_distance(a: dict[str, float], b: dict[str, float]) -> float:
    ax, ay = a.get("x", 0) + a.get("w", 0) / 2, a.get("y", 0) + a.get("h", 0) / 2
    bx, by = b.get("x", 0) + b.get("w", 0) / 2, b.get("y", 0) + b.get("h", 0) / 2
    return (ax - bx) ** 2 + (ay - by) ** 2


def _icon_slot(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "object_id": obj["object_id"],
        "semantic_role": obj.get("semantic_role"),
        "slot_type": obj.get("slot_type"),
        "size_token": obj.get("size_token"),
        "bbox_norm": obj.get("bbox_norm"),
        "bbox_in": obj.get("bbox_in"),
        "anchor_component_id": obj.get("anchor_component_id"),
        "anchor_object_id": obj.get("anchor_object_id"),
        "anchor_bbox_norm": obj.get("anchor_bbox_norm"),
        "anchor_position": obj.get("anchor_position"),
        "z_order": obj.get("z_order"),
    }


def _zone(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "object_id": obj["object_id"],
        "name": obj["name"],
        "object_type": obj["object_type"],
        "semantic_role": obj.get("semantic_role"),
        "bbox_norm": obj.get("bbox_norm"),
        "bbox_in": obj.get("bbox_in"),
        "z_order": obj.get("z_order"),
        "source_binding_id": obj.get("source_binding_id"),
        "citation_binding_id": obj.get("citation_binding_id"),
    }


def _anchor_position(slot_type: str | None) -> str:
    if slot_type in {"table_header_icon", "source_footer_icon", "citation_icon"}:
        return "inline_before_text"
    if slot_type in {"card_corner_badge_icon", "decision_marker_icon", "risk_status_icon"}:
        return "badge_corner"
    if slot_type in {"timeline_milestone_icon", "process_node_icon"}:
        return "center"
    return "center_left"
