"""Group D02 text candidates into semantic line/block candidates."""

from __future__ import annotations

from typing import Any


def group_text_lines(candidates: list[dict[str, Any]], ocr_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ocr_by_candidate = {item["candidate_id"]: item for item in ocr_results}
    sorted_candidates = sorted(candidates, key=lambda item: (item["bbox_px"][1], item["bbox_px"][0], item["candidate_id"]))
    groups: list[dict[str, Any]] = []
    for reading_order, candidate in enumerate(sorted_candidates, start=1):
        ocr = ocr_by_candidate.get(candidate["candidate_id"], {})
        bbox = candidate["bbox_px"]
        likely_slot_type = _likely_slot_from_candidate(candidate)
        groups.append(
            {
                "group_id": f"{candidate['reference_id']}_text_group_{reading_order:03d}",
                "reference_id": candidate["reference_id"],
                "candidate_ids": [candidate["candidate_id"]],
                "source_layer_ids": candidate.get("source_layer_ids") or [],
                "bbox_px": bbox,
                "bbox_norm": candidate["bbox_norm"],
                "ocr_text": ocr.get("normalized_text") or "",
                "ocr_status": ocr.get("ocr_status") or "NOT_RUN",
                "confidence": round(max(float(candidate.get("confidence") or 0.0), float(ocr.get("confidence") or 0.0)), 4),
                "reading_order": reading_order,
                "likely_slot_type": likely_slot_type,
                "content_capacity_estimate_chars": _capacity_estimate(bbox, likely_slot_type),
                "collision_protected_zone_risk": "low" if candidate.get("candidate_type") != "unknown_text_candidate" else "review",
                "notes": "One candidate per group in D02 v1; later OCR line merging can refine this.",
            }
        )
    return groups


def _likely_slot_from_candidate(candidate: dict[str, Any]) -> str:
    mapping = {
        "title_text_candidate": "title",
        "subtitle_text_candidate": "subtitle",
        "body_text_candidate": "body",
        "card_label_candidate": "card_title",
        "kpi_label_candidate": "kpi_label",
        "chart_label_candidate": "chart_title",
        "table_cell_text_candidate": "table_cell",
        "source_footer_text_candidate": "source",
        "decorative_microtext_candidate": "decorative_microtext",
        "unknown_text_candidate": "unknown_text",
    }
    return mapping.get(str(candidate.get("candidate_type")), "unknown_text")


def _capacity_estimate(bbox: list[int], slot_type: str) -> int:
    _x, _y, w, h = [int(v) for v in bbox]
    density = 0.012 if slot_type in {"source", "footer", "citation"} else 0.018
    return max(8, min(420, int(w * max(1, h) * density)))
