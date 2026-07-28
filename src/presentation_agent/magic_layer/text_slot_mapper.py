"""Map D02 text line groups to semantic slots."""

from __future__ import annotations

from typing import Any


SLOT_TYPES = {
    "title",
    "subtitle",
    "section_label",
    "section_number",
    "body",
    "card_title",
    "card_body",
    "kpi_label",
    "kpi_value",
    "chart_title",
    "chart_axis_label",
    "chart_legend",
    "table_header",
    "table_cell",
    "insight",
    "note",
    "source",
    "citation",
    "footer",
    "meta",
    "placeholder_label",
    "decorative_microtext",
    "unknown_text",
}


def map_text_slots(groups: list[dict[str, Any]]) -> dict[str, Any]:
    mappings: list[dict[str, Any]] = []
    for group in groups:
        slot_type = _normalize_slot(group.get("likely_slot_type"))
        confidence = float(group.get("confidence") or 0.0)
        disposition = "mapped"
        if slot_type == "unknown_text":
            disposition = "blocking_unresolved_unknown_text" if confidence >= 0.35 else "review_unknown_text_low_confidence"
        elif confidence < 0.35 and slot_type not in {"decorative_microtext"}:
            disposition = "mapped_low_confidence_review"
        mappings.append(
            {
                "group_id": group["group_id"],
                "slot_type": slot_type,
                "confidence": round(confidence, 4),
                "source_candidate_ids": group.get("candidate_ids") or [],
                "source_layer_ids": group.get("source_layer_ids") or [],
                "ocr_text_evidence": group.get("ocr_text") or "",
                "placeholder_text_policy": "slot_evidence_only_not_final_copy",
                "disposition": disposition,
            }
        )
    return {
        "schema_name": "semantic_text_slot_map",
        "status": "passed" if not any("blocking" in item["disposition"] for item in mappings) else "blocking_unresolved_text",
        "mappings": mappings,
        "slot_counts": {slot: sum(1 for item in mappings if item["slot_type"] == slot) for slot in sorted(SLOT_TYPES)},
    }


def _normalize_slot(value: Any) -> str:
    slot = str(value or "unknown_text")
    return slot if slot in SLOT_TYPES else "unknown_text"
