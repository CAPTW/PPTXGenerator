"""Minimal R5 fusion wrapper using only real gate-eligible proposals."""

from __future__ import annotations

from typing import Any

from .proposal_fusion import fuse_proposals


def run_minimal_stack_fusion(proposals: list[dict[str, Any]], protected_text_zones: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    real = [
        proposal
        for proposal in proposals
        if proposal.get("source_type") != "heuristic_smoke_only"
        and proposal.get("gate_eligible") is True
        and proposal.get("real_inference_ran") is True
    ]
    if not real:
        return empty_minimal_fusion("blocked_no_real_gate_eligible_proposals")
    fusion = fuse_proposals(proposals=real, protected_text_zones=protected_text_zones or [], ps_layers=[])
    return {
        "real_fused_object_graph_v2": fusion["fused_object_graph_v2"],
        "real_semantic_role_votes": fusion["semantic_role_votes"],
        "real_semantic_slot_graph": fusion["semantic_slot_graph"],
        "real_z_order_graph": fusion["z_order_graph"],
        "real_native_reconstruction_readiness_plan": fusion["native_reconstruction_readiness_plan"],
        "real_fusion_report": fusion["proposal_fusion_report"],
    }


def empty_minimal_fusion(status: str) -> dict[str, Any]:
    return {
        "real_fused_object_graph_v2": {"schema_name": "real_fused_object_graph_v2", "objects": [], "relationships": [], "canva_parity_claimed": False},
        "real_semantic_role_votes": {"schema_name": "real_semantic_role_votes", "votes": [], "canva_parity_claimed": False},
        "real_semantic_slot_graph": {"schema_name": "real_semantic_slot_graph", "slot_count": 0, "slots": [], "canva_parity_claimed": False},
        "real_z_order_graph": {"schema_name": "real_z_order_graph", "object_count": 0, "objects": [], "relationships": [], "canva_parity_claimed": False},
        "real_native_reconstruction_readiness_plan": {"schema_name": "real_native_reconstruction_readiness_plan", "objects": [], "summary": {"object_count": 0, "semantic_raster_violation_count": 0, "unknown_layer_violation_count": 0}, "canva_parity_claimed": False},
        "real_fusion_report": {"schema_name": "real_fusion_report", "status": status, "fused_object_count": 0, "canva_parity_claimed": False},
    }
