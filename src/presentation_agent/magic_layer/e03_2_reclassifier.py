"""Reclassify E03.1 before the single-slide golden placement gate."""

from __future__ import annotations

from typing import Any


DECISION = "E03_1_RECLASSIFIED_STRUCTURAL_16_PACK_PASS_OBJECT_PLACEMENT_GATE_REQUIRED"
E03_1_PASS_DECISION = "E03_1_PASS_START_E04_SOURCE_BOUND_SMALL_DECK_WITH_16_MAGIC_LAYER_PLUS_PACK"


def reclassify_e03_1(e03_1_summary: dict[str, Any]) -> dict[str, Any]:
    original_pass = e03_1_summary.get("decision") == E03_1_PASS_DECISION
    return {
        "schema_name": "e03_1_reclassification_report",
        "status": "passed" if original_pass else "blocked",
        "decision": DECISION,
        "original_decision": e03_1_summary.get("decision"),
        "structural_16_pack_status": "PASS" if original_pass else "NOT_PROVEN",
        "editability_status": "PASS",
        "no_full_slide_raster_status": "PASS",
        "semantic_raster_policy_status": "PASS",
        "visual_fidelity_status": "PATCH_REQUIRED",
        "object_placement_status": "INSUFFICIENT",
        "rendering_fidelity_status": "INSUFFICIENT",
        "generic_skeleton_regression_status": "PRESENT_OR_NOT_DISPROVEN",
        "e04_product_unlock": "REVOKED_PENDING_E03_2",
        "e04_technical_unlock": "TRUE_BUT_PRODUCT_LOCKED",
        "d08_status": "LOCKED",
        "c11_status": "FROZEN",
        "broad_canva_parity_claimed": False,
    }
