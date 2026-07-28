from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.compiler.compile_blocker import PROTECTED_OUTPUTS


def build_output_contract() -> dict[str, Any]:
    return {
        "schema": "compiler_output_contract.v1",
        "allowed_future_outputs": [
            "editable_candidate.pptx",
            "pptx_ooxml_ledger.json",
            "pptx_semantic_editability_ledger.json",
            "pptx_full_slide_raster_check.json",
            "b03_validation_report.json",
            "b01_review_packet.json",
        ],
        "forbidden_outputs": sorted(PROTECTED_OUTPUTS | {"source_bound_deck", "large_deck", "D08_C11_bulk_deck", "full_slide_raster_pptx", "screenshot_slide_pptx", "semantic_raster_fallback"}),
        "downstream_gates": ["B03_native_validation_gate", "B01_render_review_if_visual_risk"],
        "c01_outputs_future_only": True,
    }


def validate_output_contract(contract: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    allowed = [str(item).replace("\\", "/") for item in contract.get("allowed_future_outputs", [])]
    for output in allowed:
        if output in PROTECTED_OUTPUTS or "source_bound" in output.lower() or "final_deck" in output.lower() or "golden_template" in output.lower():
            failures.append(f"forbidden output listed as allowed: {output}")
    if "B03_native_validation_gate" not in contract.get("downstream_gates", []):
        failures.append("B03 downstream gate required")
    return {"schema": "compiler_output_contract_validation.v1", "pass": not failures, "failures": failures}
