"""Score repaired candidates against source truth without using truth for compilation."""

from __future__ import annotations

from typing import Any


def score_truth_reconstruction(truth: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    expected_ids = _expected_ids(truth)
    reconstructed = set(observed.get("reconstructed_object_ids", []))
    matched = [object_id for object_id in expected_ids if object_id in reconstructed or _role_proxy_match(object_id, reconstructed)]
    semantic_text_score = len([i for i in matched if "text" in i or "footer" in i]) / max(len([i for i in expected_ids if "text" in i or "footer" in i]), 1)
    depth = len(matched) / max(len(expected_ids), 1)
    required_chart_table = len(truth.get("table_chart_objects", []))
    chart_table_score = 1.0 if required_chart_table == 0 else min(1.0, observed.get("chart_table_native_count", 0) / required_chart_table)
    if observed.get("visible_internal_label_count", 0) > 0:
        depth = min(depth, 0.35)
    passed = depth >= 0.70 and semantic_text_score >= 0.75 and chart_table_score >= 0.70
    return {
        "schema_name": "fixture_truth_scoring_report",
        "status": "passed" if passed else "failed",
        "expected_object_count": len(expected_ids),
        "matched_object_count": len(matched),
        "semantic_text_reconstruction_depth": round(semantic_text_score, 3),
        "semantic_reconstruction_depth_score": round(depth, 3),
        "chart_table_truth_match_score": round(chart_table_score, 3),
        "footer_source_reconstruction_pass": "footer_source" in reconstructed or any("footer" in item for item in matched),
        "source_layer_truth_used_for_scoring_only": True,
        "canva_parity_claimed": False,
    }


def semantic_reconstruction_depth_report(score: dict[str, Any]) -> dict[str, Any]:
    payload = dict(score)
    payload["schema_name"] = "semantic_reconstruction_depth_report"
    return payload


def _expected_ids(truth: dict[str, Any]) -> list[str]:
    rows = []
    for key in ["semantic_text_objects", "semantic_icon_objects", "table_chart_objects", "card_panel_objects", "connector_vector_objects", "footer_source_objects"]:
        rows.extend(obj.get("object_id", obj.get("zone_id", "")) for obj in truth.get(key, []))
    return [item for item in rows if item]


def _role_proxy_match(object_id: str, reconstructed: set[str]) -> bool:
    if object_id.startswith("text_"):
        return any(item.startswith("pdf_text_") or item == "image_analysis_title" for item in reconstructed)
    if object_id.startswith("icon"):
        return any("icon" in item for item in reconstructed)
    if object_id == "panel_frame":
        return any("card_panel" in item or "panel" in item for item in reconstructed)
    if "panel" in object_id:
        return any("card_panel" in item or "panel" in item for item in reconstructed)
    if object_id == "accent_rule":
        return any("vector" in item or "rule" in item for item in reconstructed)
    return False
