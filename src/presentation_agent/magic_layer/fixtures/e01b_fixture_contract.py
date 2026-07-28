from __future__ import annotations

from typing import Any


CORE_REQUIRED = [
    "input/reference_image.png",
    "editable_candidate_e01b.pptx",
    "e01b_rx_decision.json",
    "e01_gate_recheck_after_e01b.json",
    "canva_plus_gate_report_e01b.json",
    "pptx_semantic_editability_ledger_e01b.json",
    "semantic_raster_violation_report_e01b.json",
]

CORE_ALTERNATIVES = {
    "input/reference_image.png": ["reference_image.png"],
    "e01b_rx_decision.json": ["e01b_rx_decision.md"],
}

OPTIONAL_PREFERRED = [
    "rendered_candidate_e01b.png",
    "reference_vs_render_e01b.png",
    "patched_object_graph_v1.json",
    "patched_layer_manifest_v5.json",
    "patched_semantic_slot_graph.json",
    "patched_native_reconstruction_plan.json",
    "patched_editable_candidate_spec.json",
    "pptx_ooxml_ledger_e01b.json",
    "pptx_full_slide_raster_check_e01b.json",
    "text_lift_target_ledger.json",
    "raster_text_suppression_plan.json",
    "unknown_layer_report_e01b.json",
    "residual_raster_text_risk_report.json",
]


def build_e01b_fixture_contract() -> dict[str, Any]:
    return {
        "schema": "e01b_required_fixture_contract.v1",
        "fixture_id": "e01b_single_reference_pass",
        "scope": "SINGLE_REFERENCE_MAGIC_LAYER_PLUS_REGRESSION",
        "core_required": CORE_REQUIRED,
        "core_alternatives": CORE_ALTERNATIVES,
        "optional_but_preferred": OPTIONAL_PREFERRED,
        "core_validation_required": {
            "b03_status": ["PASS", "PASS_WITH_LIMITATIONS"],
            "full_slide_raster_count": 0,
            "semantic_raster_violation_count": 0,
            "unknown_content_bearing_count": 0,
            "product_pass": False,
            "arbitrary_image_robustness_claim_allowed": False,
            "e03_e04_d08_unlock_allowed": False,
        },
        "pass_levels": [
            "E01B_FIXTURE_CORE_REPAIRED",
            "E01B_FIXTURE_REPAIRED_WITH_RENDER",
            "E01B_FIXTURE_REPAIRED_WITH_PROTOCOL_LIMITATIONS",
            "E01B_FIXTURE_BLOCKED_SOURCE_EVIDENCE_NOT_FOUND",
            "E01B_FIXTURE_INVALID_B03_FAIL",
        ],
        "product_pass": False,
    }

