from __future__ import annotations

from pathlib import Path
from typing import Any

from .real_reference_report import ROOT, read_json, sha256_file
from .real_reference_scope_guard import PPTX_NAME, RENDER_NAME


E01B_FIXTURE = ROOT / "design_runs/run_003/fixtures/e01b_single_reference_pass"
P03_OUT = ROOT / "design_runs/run_003/outputs/p03_rx_controlled_end_to_end_pipeline_v2_replay_minimal_sample"


def compare_with_e01b_historical(run_folder: str | Path) -> dict[str, Any]:
    run = Path(run_folder)
    semantic = read_json(run / "p04_pptx_semantic_editability_ledger.json")
    full = read_json(run / "p04_pptx_full_slide_raster_check.json")
    historical_semantic = read_json(E01B_FIXTURE / "c04_b03_revalidation/e01b_repaired_pptx_semantic_editability_ledger.json")
    historical_full = read_json(E01B_FIXTURE / "c04_b03_revalidation/e01b_repaired_pptx_full_slide_raster_check.json")
    p04_pptx_hash = sha256_file(run / PPTX_NAME)
    p04_render_hash = sha256_file(run / RENDER_NAME)
    p04_b03 = read_json(run / "p04_b03_validation_report.json")
    status = "REAL_REFERENCE_PIPELINE_PASS_WITH_LIMITATIONS"
    if not p04_pptx_hash or p04_b03.get("status") not in {"PASS", "PASS_WITH_LIMITATIONS"}:
        status = "REAL_REFERENCE_PIPELINE_FAIL"
    return {
        "schema": "p04_compare_with_e01b_historical_report.v1",
        "status": status,
        "reference_image_hash": sha256_file(E01B_FIXTURE / "input/reference_image.png"),
        "historical_e01b_pptx_hash": sha256_file(E01B_FIXTURE / "editable_candidate_e01b.pptx"),
        "historical_e01b_render_hash": sha256_file(E01B_FIXTURE / "rendered_candidate_e01b.png"),
        "p04_pptx_hash": p04_pptx_hash,
        "p04_render_hash": p04_render_hash,
        "historical_b03_status": read_json(E01B_FIXTURE / "c04_b03_revalidation/e01b_repaired_b03_validation_report.json").get("status"),
        "p04_b03_status": p04_b03.get("status"),
        "historical_full_slide_raster_count": historical_full.get("full_slide_raster_count"),
        "p04_full_slide_raster_count": full.get("full_slide_raster_count"),
        "historical_semantic_raster_violation_count": historical_semantic.get("semantic_raster_violation_count"),
        "p04_semantic_raster_violation_count": semantic.get("semantic_raster_violation_count"),
        "historical_unknown_content_bearing_count": historical_semantic.get("unknown_content_bearing_count"),
        "p04_unknown_content_bearing_count": semantic.get("unknown_content_bearing_count"),
        "visual_fidelity_required": False,
        "claim_scope": "single real-reference controlled pipeline only",
        "limitations": ["P04 does not need to visually match historical E01B perfectly", "historical E01B remains regression fixture baseline"],
        "product_pass": False,
    }


def compare_with_p03_minimal_pipeline(run_folder: str | Path) -> dict[str, Any]:
    run = Path(run_folder)
    p04_b03 = read_json(run / "p04_b03_validation_report.json")
    p04_review = read_json(run / "p04_b01_review_packet.json")
    p03_b03 = read_json(P03_OUT / "p03_pptx_b03_validation_report.json")
    p03_review = read_json(P03_OUT / "p03_b01_review_packet.json")
    status = "REAL_REFERENCE_PIPELINE_PASS_WITH_LIMITATIONS"
    if p04_b03.get("status") not in {"PASS", "PASS_WITH_LIMITATIONS"}:
        status = "REAL_REFERENCE_PIPELINE_FAIL"
    return {
        "schema": "p04_compare_with_p03_minimal_pipeline_report.v1",
        "status": status,
        "p03_scope": "minimal synthetic controlled sample",
        "p04_scope": "repaired E01B real-reference controlled sample",
        "p03_pptx_hash": sha256_file(P03_OUT / "p03_controlled_minimal_editable_candidate.pptx"),
        "p04_pptx_hash": sha256_file(run / PPTX_NAME),
        "p03_render_hash": sha256_file(P03_OUT / "p03_controlled_minimal_rendered_slide.png"),
        "p04_render_hash": sha256_file(run / RENDER_NAME),
        "p03_b03_status": p03_b03.get("status"),
        "p04_b03_status": p04_b03.get("status"),
        "p03_review_status": p03_review.get("decision"),
        "p04_review_status": p04_review.get("decision"),
        "render_is_reference_image": False,
        "product_pass": False,
        "limitations": ["P04 expands from minimal sample to one repaired real-reference fixture, not arbitrary robustness"],
    }
