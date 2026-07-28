"""Reclassify E02 before the E02.1 reference-fidelity patch."""

from __future__ import annotations

from typing import Any


DECISION = "E02_RECLASSIFIED_STRUCTURAL_PASS_VISUAL_FIDELITY_PATCH_REQUIRED"


def reclassify_e02(e02_decision_summary: dict[str, Any], e02_gate_report: dict[str, Any]) -> dict[str, Any]:
    structural_pass = e02_decision_summary.get("decision") == "E02_PASS_START_E03_16_ARCHETYPE_MAGIC_LAYER_PLUS_TEMPLATE_PACK"
    gate_pass = e02_gate_report.get("status") == "passed"
    return {
        "schema_name": "e02_reclassification_report",
        "decision": DECISION,
        "status": "passed" if structural_pass and gate_pass else "blocked",
        "e02_structural_conversion_status": "PASS" if structural_pass else "NOT_PROVEN",
        "e02_editability_policy_status": "PASS",
        "e02_no_raster_policy_status": "PASS",
        "e02_pack_created_status": "PASS_NON_CANONICAL" if e02_decision_summary.get("pack_created") else "NOT_CREATED",
        "e02_broad_canva_parity_claimed": False,
        "e02_visual_reference_fidelity_status": "INSUFFICIENT",
        "e02_magic_layer_plus_4core_status": "NOT_PROVEN",
        "e03_product_unlock": "REVOKED_PENDING_E02_1",
        "e03_technical_unlock": "TRUE_BUT_PRODUCT_LOCKED",
        "reason": "E02 passed structural/editability/raster policy gates but produced editable skeletons rather than reference-faithful Magic Layer+ reconstructions.",
    }
