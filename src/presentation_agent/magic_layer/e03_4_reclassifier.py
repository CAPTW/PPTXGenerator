"""Reclassify E03.3 before the E03.4 icon foundation gate."""

from __future__ import annotations

from typing import Any


RECLASSIFICATION_DECISION = "E03_3_RECLASSIFIED_STRUCTURAL_PASS_ICON_PICTOGRAM_FOUNDATION_REQUIRED"


def reclassify_e03_3(e03_3_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e03_3_reclassification_report",
        "decision": RECLASSIFICATION_DECISION,
        "original_decision": e03_3_summary.get("decision"),
        "e03_3_structural_object_placement_status": "PASS",
        "e03_3_editability_status": "PASS",
        "e03_3_no_full_slide_raster_status": "PASS",
        "e03_3_icon_pictogram_fidelity_status": "INSUFFICIENT",
        "e03_3_curated_icon_library_status": "NOT_PRODUCT_READY",
        "e03_3_product_magic_layer_plus_status": "NOT_READY_FOR_E04",
        "e04_unlock_status": "REVOKED_PENDING_E03_4",
        "e03_5_unlock_status": "LOCKED",
        "d08_status": "LOCKED",
        "c11_status": "LOCKED",
        "bulk_scaleout_status": "LOCKED",
        "broad_canva_parity_claimed": bool(e03_3_summary.get("broad_canva_parity_claimed", False)),
        "protected_artifacts_unchanged": bool(e03_3_summary.get("protected_artifacts_unchanged", True)),
    }
