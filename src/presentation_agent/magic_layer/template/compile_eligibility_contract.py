from __future__ import annotations

from typing import Any


def compile_eligibility_contract() -> dict[str, Any]:
    return {
        "schema": "compile_eligibility_contract.v1",
        "required_inputs": ["psd_like_layer_model_or_equivalent", "object_graph", "layer_manifest", "semantic_slot_graph", "template_contract", "slot_schema", "native_reconstruction_plan"],
        "required_precompile_gates": ["E01P_protocol_gate", "graph_consistency", "targetability", "semantic_raster_precompile", "unknown_layer_policy", "template_contract_validation", "slot_schema_validation", "native_reconstruction_plan_validation"],
        "required_output_obligations": ["editable_candidate_spec_for_future_stage"],
        "blocked_conditions": ["unknown_content_bearing > 0", "semantic_raster_precompile_violations > 0", "full_slide_raster_plan > 0", "required_slot_missing", "required_slot_not_editable", "required_native_component_explicit_reject", "chart_table_timeline_matrix_roadmap_raster_fallback", "footer_source_slot_raster", "text_overflow_policy_missing", "manual_review_artifact_used", "quarantined_artifact_used"],
        "downstream_validation_obligations": ["B03_native_validation_gate"],
        "review_obligations": ["B01_render_review_if_visual_risk"],
        "decision_values": ["COMPILE_ELIGIBLE", "COMPILE_ELIGIBLE_WITH_WARNINGS", "NOT_COMPILE_ELIGIBLE", "BLOCKED_MISSING_INPUT", "BLOCKED_FATAL_POLICY", "BLOCKED_MANUAL_REVIEW", "BLOCKED_QUARANTINE", "BLOCKED_PROTECTED_ARTIFACTS"],
        "product_pass": False,
    }
