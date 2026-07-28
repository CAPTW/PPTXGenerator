"""Resolve triaged table/matrix regions into editable table skeleton specs."""

from __future__ import annotations

from typing import Any

from .native_table_taxonomy import table_type_for_reference


def resolve_true_table_regions(reference_id: str, triage: dict[str, Any]) -> dict[str, Any]:
    true_items = [item for item in triage.get("triaged_candidates") or [] if item["triage_class"] in {"true_table_region", "true_matrix_region"}]
    cell_items = [item for item in triage.get("triaged_candidates") or [] if item["triage_class"] == "table_header_or_cell_group"]
    table_candidates = []
    if true_items:
        table_candidates.append(_aggregate_table_candidate(reference_id, true_items, cell_items))
    risk = ""
    if reference_id == "table_heavy" and not table_candidates:
        risk = "table_heavy_table_absence_requires_explicit_blocker"
    return {
        "schema_name": "true_table_region_candidates",
        "reference_id": reference_id,
        "status": "passed" if table_candidates else "no_table_semantics_detected",
        "table_candidates": table_candidates,
        "table_header_cell_candidates": cell_items,
        "risk": risk,
    }


def build_native_table_spec(reference_id: str, table_candidates: dict[str, Any]) -> dict[str, Any]:
    specs = []
    for index, candidate in enumerate(table_candidates.get("table_candidates") or [], start=1):
        table_type = table_type_for_reference(reference_id)
        specs.append(
            {
                "native_table_spec_id": f"{reference_id}_native_table_{index:02d}",
                "source_candidate_ids": candidate["source_candidate_ids"],
                "source_layer_ids": candidate["source_layer_ids"],
                "bbox_px": candidate["bbox_px"],
                "bbox_norm": candidate["bbox_norm"],
                "table_component_type": table_type,
                "target_ppt_object_type": "editable_shape_grid_table",
                "native_ppt_table_possible": table_type in {"native_ppt_table", "evidence_inventory_table", "citation_column"},
                "editable_shape_grid_possible": True,
                "table_skeleton_spec": {
                    "source_data_required_for_final_conversion": True,
                    "row_count_inferred": candidate["row_count_estimate"],
                    "column_count_inferred": candidate["column_count_estimate"],
                    "data_values_inferred": False,
                    "unresolved_structure_reason": "OCR unavailable; D04 estimates capacity from grid-like geometry and requires source data later.",
                },
                "header_body_citation_policy": "editable text or native/shape-grid table cells",
                "source_citation_hooks": ["source_id", "citation_id", "row_source_ref", "cell_source_ref"],
                "raster_final_use_policy": "forbidden_for_semantic_table",
                "D05_render_fidelity_requirements": ["render_compare", "cell_readability", "no_semantic_table_raster"],
            }
        )
    return {
        "schema_name": "native_table_spec",
        "reference_id": reference_id,
        "status": "passed" if specs else "no_native_table_spec",
        "table_specs": specs,
        "risk": table_candidates.get("risk") or "",
    }


def _aggregate_table_candidate(reference_id: str, true_items: list[dict[str, Any]], cell_items: list[dict[str, Any]]) -> dict[str, Any]:
    source = true_items + cell_items
    boxes = [item["bbox_px"] for item in source]
    return {
        "candidate_id": f"{reference_id}_table_skeleton_01",
        "source_candidate_ids": [item["candidate_id"] for item in source],
        "source_layer_ids": sorted({layer_id for item in source for layer_id in item.get("source_layer_ids") or []}),
        "bbox_px": _union_bbox(boxes),
        "bbox_norm": _union_bbox_norm([item.get("bbox_norm") for item in source if item.get("bbox_norm")]),
        "table_component_type_candidate": table_type_for_reference(reference_id),
        "row_count_estimate": _estimate_rows(boxes),
        "column_count_estimate": _estimate_columns(boxes),
        "confidence": round(sum(item["confidence"] for item in true_items) / len(true_items), 4),
        "data_values_inferred": False,
        "source_data_required_for_final_conversion": True,
    }


def _estimate_rows(boxes: list[list[int]]) -> int:
    ys = sorted({round(box[1] / 36) for box in boxes})
    return max(2, min(8, len(ys)))


def _estimate_columns(boxes: list[list[int]]) -> int:
    xs = sorted({round(box[0] / 120) for box in boxes})
    return max(2, min(6, len(xs)))


def _union_bbox(boxes: list[list[int]]) -> list[int]:
    x1 = min(box[0] for box in boxes)
    y1 = min(box[1] for box in boxes)
    x2 = max(box[0] + box[2] for box in boxes)
    y2 = max(box[1] + box[3] for box in boxes)
    return [x1, y1, x2 - x1, y2 - y1]


def _union_bbox_norm(boxes: list[list[float]]) -> list[float]:
    x1 = min(box[0] for box in boxes)
    y1 = min(box[1] for box in boxes)
    x2 = max(box[0] + box[2] for box in boxes)
    y2 = max(box[1] + box[3] for box in boxes)
    return [round(x1, 6), round(y1, 6), round(x2 - x1, 6), round(y2 - y1, 6)]

