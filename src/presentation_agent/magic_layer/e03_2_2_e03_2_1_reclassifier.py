"""Reclassify E03.2.1 before the icon hygiene gate."""

from __future__ import annotations

from typing import Any


PASS_DECISION = "E03_2_1_PASS_START_E03_3_BATCH_OBJECT_PLACEMENT_GENERALIZATION"
RECLASS_DECISION = "E03_2_1_RECLASSIFIED_STRUCTURAL_ICON_LIBRARY_PASS_CROP_HYGIENE_PATCH_REQUIRED"


def reclassify_e03_2_1(previous_report: dict[str, Any] | None = None) -> dict[str, Any]:
    previous_report = previous_report or {}
    return {
        "schema_name": "e03_2_1_reclassification_report",
        "status": "passed",
        "decision": RECLASS_DECISION,
        "previous_decision": previous_report.get("decision"),
        "previous_decision_was_icon_library_pass": previous_report.get("decision") == PASS_DECISION,
        "e03_2_1_icon_inventory_status": "STRUCTURAL_PASS",
        "e03_2_1_curated_v3_status": "STRUCTURAL_PASS",
        "e03_2_1_generated_svg_status": "PARTIAL_PASS",
        "e03_2_1_crop_hygiene_status": "INSUFFICIENT",
        "e03_2_1_false_positive_filter_status": "INSUFFICIENT",
        "e03_2_1_glyph_only_crop_status": "INSUFFICIENT",
        "e03_2_1_vision_trace_input_quality": "INSUFFICIENT",
        "e03_3_unlock_status": "REVOKED_PENDING_E03_2_2",
        "e04_status": "LOCKED",
        "broad_canva_parity_claimed": False,
    }
