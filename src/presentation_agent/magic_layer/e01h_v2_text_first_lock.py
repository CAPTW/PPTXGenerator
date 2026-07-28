"""Protect semantic text zones before visual backplate planning."""

from __future__ import annotations

from typing import Any


def build_text_first_lock(case: dict[str, Any], pdf_signal_report: dict[str, Any]) -> dict[str, Any]:
    truth = case.get("source_layer_truth", {})
    text_objects = truth.get("semantic_text_objects", []) + truth.get("footer_source_objects", [])
    return {
        "schema_name": "text_first_lock_report",
        "status": "passed" if text_objects else "partial",
        "case_id": case["case_id"],
        "protected_text_zone_count": len(text_objects),
        "pdf_text_signal_used": pdf_signal_report.get("status") == "passed",
        "semantic_text_absorbed_into_backplate": False,
        "footer_treated_as_decorative_raster": False,
        "protected_zones": text_objects,
        "canva_parity_claimed": False,
    }
