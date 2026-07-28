from __future__ import annotations

from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
CONTROLLED_SAMPLE_ID = "controlled_minimal_cover_hero_v1"
C02B_HASH = "af09ecb032d9b187d8ceafb08b41097b1dcfc767dd079253237c781a0883559c"
C03A_RENDER_HASH = "d86c689509e6d58b0a295208ac02f5490afd4f0e88bf4e1b2e47953dd8e54edb"


PATHS = {
    "t02_editable_candidate_spec": ROOT / "design_runs/run_003/outputs/t02_rx_native_reconstruction_planner_editable_spec_builder/planner_sample_outputs/minimal_cover_hero_editable_candidate_spec.json",
    "t02_compiler_input_bundle": ROOT / "design_runs/run_003/outputs/t02_rx_native_reconstruction_planner_editable_spec_builder/planner_sample_outputs/minimal_cover_hero_compiler_input_bundle.json",
    "c01_dry_run_report": ROOT / "design_runs/run_003/outputs/c01_rx_contract_aware_pptx_compiler_skeleton_dry_run/compiler_sample_outputs/minimal_cover_hero_dry_run_report.json",
    "c01_primitive_plan": ROOT / "design_runs/run_003/outputs/c01_rx_contract_aware_pptx_compiler_skeleton_dry_run/compiler_sample_outputs/minimal_cover_hero_pptx_primitive_plan.json",
    "c02_original_pptx": ROOT / "design_runs/run_003/outputs/c02_rx_controlled_minimal_pptx_compile/controlled_minimal_editable_candidate.pptx",
    "c02b_patched_pptx": ROOT / "design_runs/run_003/outputs/c02b_rx_patch_minimal_ooxml_backend_compatibility/controlled_minimal_editable_candidate_c02b.pptx",
    "c02b_openability_report": ROOT / "design_runs/run_003/outputs/c02b_rx_patch_minimal_ooxml_backend_compatibility/patched_pptx_powerpoint_openability_preflight.json",
    "c02b_b03_report": ROOT / "design_runs/run_003/outputs/c02b_rx_patch_minimal_ooxml_backend_compatibility/patched_pptx_b03_validation_report.json",
    "c03a_retry_render": ROOT / "design_runs/run_003/outputs/c03a_rx_retry_render_c02b_powerpoint_openable_pptx/controlled_minimal_c02b_rendered_slide.png",
    "c03a_retry_b01_review_packet": ROOT / "design_runs/run_003/outputs/c03a_rx_retry_render_c02b_powerpoint_openable_pptx/controlled_retry_b01_review_packet.json",
    "c03a_retry_overlay_document": ROOT / "design_runs/run_003/outputs/c03a_rx_retry_render_c02b_powerpoint_openable_pptx/controlled_retry_overlay_document.json",
    "c03a_retry_visual_smoke_review": ROOT / "design_runs/run_003/outputs/c03a_rx_retry_render_c02b_powerpoint_openable_pptx/controlled_retry_visual_smoke_review.json",
    "c03a_retry_scaleout_report": ROOT / "design_runs/run_003/outputs/c03a_rx_retry_render_c02b_powerpoint_openable_pptx/scaleout_lock_recheck_report.json",
}


def build_controlled_sample_artifact_map() -> dict[str, Any]:
    artifacts = []
    for artifact_id, path in PATHS.items():
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "path": str(path),
                "exists": path.is_file(),
                "expected_hash": C02B_HASH if artifact_id == "c02b_patched_pptx" else C03A_RENDER_HASH if artifact_id == "c03a_retry_render" else None,
                "class": _class_for(artifact_id),
                "role": _role_for(artifact_id),
                "product_pass_allowed": False,
                "limitations": ["controlled_minimal_scope_only"],
            }
        )
    return {"schema": "controlled_sample_artifact_map.v1", "sample_id": CONTROLLED_SAMPLE_ID, "artifacts": artifacts, "product_pass": False}


def _class_for(artifact_id: str) -> str:
    if "pptx" in artifact_id:
        return "CONTROLLED_PPTX"
    if "render" in artifact_id:
        return "RENDER_ARTIFACT"
    if "b03" in artifact_id:
        return "B03_VALIDATION_ARTIFACT"
    if "b01" in artifact_id or "overlay" in artifact_id or "visual" in artifact_id:
        return "B01_REVIEW_ARTIFACT"
    if "t02" in artifact_id:
        return "PLANNER_ARTIFACT"
    if "c01" in artifact_id:
        return "DRY_RUN_ARTIFACT"
    return "CLAIM_BOUNDARY_ARTIFACT"


def _role_for(artifact_id: str) -> str:
    if artifact_id == "c02_original_pptx":
        return "historical_superseded_by_c02b"
    if artifact_id == "c03a_retry_render":
        return "diagnostic_render_not_reference_input"
    return "controlled_sample_evidence"
