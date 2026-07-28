"""Strict E01 Canva Magic Layer+ gate evaluation."""

from __future__ import annotations

from typing import Any

from .magic_layer_plus_gate import REQUIRED_OBJECT_GRAPH_ARTIFACTS


CANVA_BENCHMARK_SHAPE_COUNT = 53
CANVA_BENCHMARK_EDITABLE_TEXT_COUNT = 26
CANVA_BENCHMARK_RASTER_SEGMENT_COUNT = 27


PASS_DECISION = "E01_PASS_START_E02_4CORE_MAGIC_LAYER_PLUS"


def evaluate_e01_canva_plus_gate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one reference-image-to-editable-PPT candidate against the E01 gate.

    The gate deliberately separates structural success from product unlock. A
    candidate can compile, render, and produce editable objects while still
    remaining blocked for E02 when OCR/text lift or reference-vs-render fidelity
    is not proven.
    """

    artifacts = set(candidate.get("artifacts") or [])
    missing = [name for name in REQUIRED_OBJECT_GRAPH_ARTIFACTS if name not in artifacts]
    failures: list[str] = []
    high_product_risks: list[str] = []

    if missing:
        failures.append("missing_required_artifacts")
    if candidate.get("candidate_renders") is not True:
        failures.append("candidate_render_missing")
    if candidate.get("full_slide_reference_background") is True:
        failures.append("full_slide_reference_background_forbidden")
    if candidate.get("screenshot_slide") is True:
        failures.append("screenshot_slide_forbidden")
    if candidate.get("semantic_text_editable") is not True:
        failures.append("semantic_text_not_editable")
    if candidate.get("source_footer_native") is not True:
        failures.append("source_footer_not_native")
    if candidate.get("cards_panels_native") is not True:
        failures.append("cards_panels_not_native")
    if int(candidate.get("semantic_raster_violation_count", 0)) > 0:
        failures.append("semantic_raster_violations_present")
    if int(candidate.get("unknown_content_bearing_layer_count", 0)) > 0:
        failures.append("unknown_content_bearing_layers_present")

    object_count = int(candidate.get("object_graph_node_count", 0))
    editable_text_count = int(candidate.get("editable_text_count", 0))
    visual_layer_count = int(candidate.get("visual_layer_count", 0))
    if object_count < CANVA_BENCHMARK_SHAPE_COUNT:
        failures.append("object_graph_density_below_canva_boundary")
    if visual_layer_count < CANVA_BENCHMARK_SHAPE_COUNT:
        failures.append("visual_layer_density_below_canva_boundary")
    if editable_text_count < CANVA_BENCHMARK_EDITABLE_TEXT_COUNT:
        failures.append("editable_text_density_below_canva_boundary")

    if candidate.get("ocr_backend") == "unavailable":
        high_product_risks.append("ocr_unavailable_text_geometry_only")
    if candidate.get("text_final_copy_policy") != "recognized_reference_text":
        high_product_risks.append("reference_text_not_lifted_no_final_copy_inferred")

    fidelity_status = candidate.get("reference_vs_render_fidelity")
    if fidelity_status not in {"acceptable", "pass", "strong"}:
        high_product_risks.append("reference_vs_render_fidelity_not_acceptable")

    status = "passed" if not failures and not high_product_risks else "failed"
    decision = _decision_for(failures, high_product_risks)
    return {
        "schema_name": "canva_plus_gate_report",
        "status": status,
        "decision": decision,
        "e02_unlocked": decision == PASS_DECISION,
        "failures": failures,
        "high_product_risks": high_product_risks,
        "missing_artifacts": missing,
        "benchmark": {
            "canva_shape_count": CANVA_BENCHMARK_SHAPE_COUNT,
            "canva_editable_text_count": CANVA_BENCHMARK_EDITABLE_TEXT_COUNT,
            "canva_raster_segment_count": CANVA_BENCHMARK_RASTER_SEGMENT_COUNT,
        },
        "candidate": {
            "object_graph_node_count": object_count,
            "visual_layer_count": visual_layer_count,
            "editable_text_count": editable_text_count,
            "candidate_renders": candidate.get("candidate_renders") is True,
            "semantic_raster_violation_count": int(candidate.get("semantic_raster_violation_count", 0)),
            "unknown_content_bearing_layer_count": int(candidate.get("unknown_content_bearing_layer_count", 0)),
            "reference_vs_render_fidelity": fidelity_status,
        },
        "canva_parity_claimed": decision == PASS_DECISION,
        "canva_parity_claim_note": "Parity may be claimed only for this single-reference E01 gate when the pass decision is emitted.",
    }


def _decision_for(failures: list[str], high_product_risks: list[str]) -> str:
    if any("semantic" in failure for failure in failures):
        return "E01_FAIL_SEMANTIC_EDITABILITY"
    if any("density_below_canva" in failure for failure in failures):
        return "E01_FAIL_CANVA_LAYER_TARGET"
    if "reference_vs_render_fidelity_not_acceptable" in high_product_risks:
        return "E01_PATCH_RENDER_FIDELITY"
    if any(risk.startswith("ocr_unavailable") or "text_not_lifted" in risk or "reference_text" in risk for risk in high_product_risks):
        return "E01_PATCH_TEXT_REGION_LIFT"
    if failures:
        return "E01_PATCH_OBJECT_GRAPH_EXTRACTION"
    return PASS_DECISION

