"""Editable text layer spec builder for D02."""

from __future__ import annotations

from typing import Any


def build_editable_text_layer_spec(
    reference_id: str,
    groups: list[dict[str, Any]],
    slot_map: dict[str, Any],
    ocr_results: list[dict[str, Any]],
) -> dict[str, Any]:
    mapping_by_group = {item["group_id"]: item for item in slot_map.get("mappings") or []}
    ocr_by_candidate = {item["candidate_id"]: item for item in ocr_results}
    specs = []
    for index, group in enumerate(groups, start=1):
        mapping = mapping_by_group.get(group["group_id"], {})
        candidate_id = (group.get("candidate_ids") or [None])[0]
        ocr = ocr_by_candidate.get(candidate_id, {})
        slot_type = mapping.get("slot_type") or group.get("likely_slot_type") or "unknown_text"
        confidence = max(float(group.get("confidence") or 0.0), float(mapping.get("confidence") or 0.0))
        unresolved_reason = ""
        if "blocking" in str(mapping.get("disposition")):
            unresolved_reason = str(mapping.get("disposition"))
        elif confidence < 0.35 and slot_type not in {"decorative_microtext"}:
            unresolved_reason = "low_confidence_text_layer"
        specs.append(
            {
                "text_layer_id": f"{reference_id}_editable_text_{index:03d}",
                "reference_id": reference_id,
                "source_layer_ids": group.get("source_layer_ids") or [],
                "source_candidate_ids": group.get("candidate_ids") or [],
                "bbox_px": group["bbox_px"],
                "bbox_norm": group["bbox_norm"],
                "slot_type": slot_type,
                "placeholder_or_ocr_text": ocr.get("normalized_text") or None,
                "ocr_status": ocr.get("ocr_status") or "NOT_RUN",
                "text_role": slot_type,
                "font_size_estimate": _font_size_estimate(group["bbox_px"], slot_type),
                "font_weight_estimate": _font_weight_estimate(slot_type),
                "color_estimate": "unknown_pending_D05",
                "alignment_estimate": _alignment_estimate(group["bbox_norm"], slot_type),
                "capacity_estimate_chars": group.get("content_capacity_estimate_chars"),
                "overflow_risk": _overflow_risk(group.get("content_capacity_estimate_chars", 0), slot_type),
                "editability_target": "ppt_text",
                "confidence": round(confidence, 4),
                "unresolved_reason": unresolved_reason,
                "final_copy_allowed": False,
            }
        )
    return {
        "schema_name": "editable_text_layer_spec",
        "reference_id": reference_id,
        "status": "passed" if not any(item["unresolved_reason"].startswith("blocking") for item in specs) else "blocking",
        "text_layers": specs,
    }


def validate_editable_text_layer(layer: dict[str, Any]) -> list[str]:
    required = {
        "text_layer_id",
        "reference_id",
        "source_layer_ids",
        "bbox_px",
        "bbox_norm",
        "slot_type",
        "placeholder_or_ocr_text",
        "text_role",
        "font_size_estimate",
        "capacity_estimate_chars",
        "overflow_risk",
        "editability_target",
        "confidence",
        "unresolved_reason",
    }
    errors = []
    missing = required.difference(layer)
    if missing:
        errors.append(f"missing_fields:{','.join(sorted(missing))}")
    if layer.get("editability_target") != "ppt_text":
        errors.append("editability_target_must_be_ppt_text")
    if layer.get("confidence") is None:
        errors.append("confidence_required")
    return errors


def _font_size_estimate(bbox: list[int], slot_type: str) -> int:
    _x, _y, _w, h = [int(v) for v in bbox]
    if slot_type == "title":
        return max(24, min(44, int(h * 0.42)))
    if slot_type in {"subtitle", "section_label"}:
        return max(14, min(26, int(h * 0.34)))
    if slot_type in {"source", "footer", "citation", "decorative_microtext"}:
        return max(6, min(10, int(h * 0.22)))
    return max(9, min(18, int(h * 0.26)))


def _font_weight_estimate(slot_type: str) -> str:
    return "bold" if slot_type in {"title", "section_number", "kpi_value", "table_header", "chart_title"} else "regular"


def _alignment_estimate(bbox_norm: list[float], slot_type: str) -> str:
    if slot_type in {"source", "footer", "citation"}:
        return "left"
    x = float(bbox_norm[0])
    return "right" if x > 0.62 else "left"


def _overflow_risk(capacity: int, slot_type: str) -> str:
    if slot_type in {"source", "footer", "citation"} and capacity < 24:
        return "medium"
    if capacity < 16 and slot_type not in {"decorative_microtext"}:
        return "medium"
    return "low"
