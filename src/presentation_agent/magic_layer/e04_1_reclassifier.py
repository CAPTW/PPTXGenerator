"""Reclassify E04 before the E04.1 icon micro-placement patch."""

from __future__ import annotations


def reclassify_e04_for_icon_micro_placement() -> dict[str, object]:
    return {
        "schema_name": "e04_reclassification_report",
        "decision": "E04_RECLASSIFIED_SOURCE_BOUND_PASS_ICON_MICRO_PLACEMENT_REQUIRED",
        "original_decision": "E04_PASS_START_E05_SOURCE_BOUND_PRODUCT_REVIEW",
        "source_binding_status": "PASS",
        "citation_binding_status": "PASS",
        "slot_binding_status": "PASS",
        "contract_v2_status": "PASS",
        "icon_v7_1_visibility_status": "PASS",
        "semantic_icon_slot_anchoring_status": "PATCH_REQUIRED",
        "icon_size_position_detail_status": "PATCH_REQUIRED",
        "diagnostic_icon_leakage_risk": "HIGH_UNTIL_PROVEN_FALSE",
        "e05_unlock_status": "REVOKED_PENDING_E04_1",
        "e05_status": "LOCKED",
        "d08_status": "LOCKED",
        "c11_status": "LOCKED",
        "broad_canva_parity_claimed": False,
    }
