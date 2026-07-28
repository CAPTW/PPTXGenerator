"""Reclassify E03 before the E03.1 reference-fidelity patch."""

from __future__ import annotations

from typing import Any


DECISION = "E03_RECLASSIFIED_STRUCTURAL_PASS_REFERENCE_FIDELITY_PATCH_REQUIRED"


def reclassify_e03(e03_decision_summary: dict[str, Any]) -> dict[str, Any]:
    original_pass = e03_decision_summary.get("decision") == "E03_PASS_START_E04_SOURCE_BOUND_SMALL_DECK_WITH_16_MAGIC_LAYER_PLUS_PACK"
    return {
        "schema_name": "e03_reclassification_report",
        "status": "passed" if original_pass else "blocked",
        "decision": DECISION,
        "e03_original_decision": e03_decision_summary.get("decision"),
        "e03_structural_status": "PASS" if original_pass else "NOT_PROVEN",
        "e03_editability_status": "PASS",
        "e03_no_full_slide_raster_status": "PASS",
        "e03_semantic_raster_policy_status": "PASS",
        "e03_pack_assembly_status": "PASS_NON_CANONICAL" if e03_decision_summary.get("pack_created") else "NOT_CREATED",
        "e03_reference_fidelity_status": "PATCH_REQUIRED",
        "e03_expansion_archetype_visual_identity_status": "INSUFFICIENT_FOR_E04_PRODUCT_UNLOCK",
        "e04_product_unlock": "REVOKED_PENDING_E03_1",
        "e04_technical_unlock": "TRUE_BUT_PRODUCT_LOCKED",
        "d08_status": "LOCKED",
        "c11_status": "FROZEN",
        "bulk_scaleout_status": "LOCKED",
        "broad_canva_parity_claimed": False,
    }
