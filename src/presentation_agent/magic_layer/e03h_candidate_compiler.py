"""E03H candidate compiler wrappers."""

from __future__ import annotations

from src.presentation_agent.magic_layer.e02h_candidate_compiler import (
    audit_e02h_candidate_pptx,
    build_e02h_editable_candidate_spec,
    build_e02h_inventory_ledgers,
    compile_e02h_candidate,
    render_e02h_candidate_preview,
)


def compile_e03h_candidate(payload, output_dir):
    return compile_e02h_candidate(payload, output_dir)


def render_e03h_candidate_preview(payload, output_dir):
    return render_e02h_candidate_preview(payload, output_dir)


def audit_e03h_candidate_pptx(pptx_path):
    return audit_e02h_candidate_pptx(pptx_path)


def build_e03h_editable_candidate_spec(payload):
    spec = build_e02h_editable_candidate_spec(payload)
    spec["conversion_mode"] = "e03h_high_fidelity_hybrid_reference_pack"
    return spec


def build_e03h_inventory_ledgers(inventory, payload):
    return build_e02h_inventory_ledgers(inventory, payload)
