"""Audit reconstruction depth against fixture truth manifests."""

from __future__ import annotations

from typing import Any


GENERIC_VISIBLE_TEXT = [
    "PDF/PPT-like conversion benchmark",
    "Editable semantic layer",
    "Bounded visual backplate",
    "Local E01H-V2 validation case",
    "Hybrid backplate + editable semantic native layers",
]


def audit_fixture_truth_reconstruction(truth: dict[str, Any], semantic_plan: dict[str, Any], visible_text: list[str]) -> dict[str, Any]:
    expected = _expected_objects(truth)
    mappings = semantic_plan.get("mappings", {})
    mapped = [obj for obj in expected if obj.get("object_id") in mappings]
    generic = any(label.lower() in "\n".join(visible_text).lower() for label in GENERIC_VISIBLE_TEXT)
    mapping_score = len(mapped) / max(len(expected), 1)
    component_depth = 0.35 if generic else min(1.0, mapping_score)
    if _required_chart_or_table_generic(truth, visible_text):
        component_depth = min(component_depth, 0.45)
    status = "passed" if component_depth >= 0.70 and not generic else "failed"
    return {
        "schema_name": "fixture_truth_reconstruction_report",
        "status": status,
        "expected_semantic_object_count": len(expected),
        "mapped_semantic_object_count": len(mapped),
        "generic_placeholder_content_detected": generic,
        "semantic_reconstruction_depth_score": round(component_depth, 3),
        "chart_table_truth_mapping_pass": not _required_chart_or_table_generic(truth, visible_text),
        "expected_semantic_objects_replaced_by_generic_boxes": generic,
        "canva_parity_claimed": False,
    }


def _expected_objects(truth: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key in ["semantic_text_objects", "semantic_icon_objects", "table_chart_objects", "card_panel_objects", "connector_vector_objects", "footer_source_objects"]:
        rows.extend(truth.get(key, []))
    return rows


def _required_chart_or_table_generic(truth: dict[str, Any], visible_text: list[str]) -> bool:
    required = bool(truth.get("table_chart_objects"))
    text = "\n".join(visible_text).lower()
    return required and ("editable semantic layer" in text or "bounded visual backplate" in text)
