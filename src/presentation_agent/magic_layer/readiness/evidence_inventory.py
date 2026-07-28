from __future__ import annotations

import json
from pathlib import Path
from typing import Any


STAGE_PATHS = {
    "A01": ("design_runs/run_003/outputs/a01_rx_artifact_registry_claim_verification_cli", "a01_rx_decision.json", "GOVERNANCE_EVIDENCE"),
    "B03": ("design_runs/run_003/outputs/b03_rx_pptx_native_validation_cli_hardening", "b03_rx_decision.json", "VALIDATION_EVIDENCE"),
    "E01P": ("design_runs/run_003/outputs/e01p_rx_psd_like_layer_mask_selection_protocol", "e01p_rx_decision.json", "PROTOCOL_EVIDENCE"),
    "B01": ("design_runs/run_003/outputs/b01_rx_render_review_workbench", "b01_rx_decision.json", "REVIEW_EVIDENCE"),
    "T01": ("design_runs/run_003/outputs/t01_rx_template_contract_slot_schema_hardening", "t01_rx_decision.json", "PROTOCOL_EVIDENCE"),
    "T02": ("design_runs/run_003/outputs/t02_rx_native_reconstruction_planner_editable_spec_builder", "t02_rx_decision.json", "PROTOCOL_EVIDENCE"),
    "C01": ("design_runs/run_003/outputs/c01_rx_contract_aware_pptx_compiler_skeleton_dry_run", "c01_rx_decision.json", "COMPILER_EVIDENCE"),
    "C02B": ("design_runs/run_003/outputs/c02b_rx_patch_minimal_ooxml_backend_compatibility", "c02b_rx_decision.json", "COMPILER_EVIDENCE"),
    "C03A_RETRY": ("design_runs/run_003/outputs/c03a_rx_retry_render_c02b_powerpoint_openable_pptx", "c03a_retry_decision.json", "RENDER_EVIDENCE"),
    "P02": ("design_runs/run_003/outputs/p02_rx_magic_layer_pipeline_v2_orchestrator_controlled_sample_flow", "p02_rx_decision.json", "READINESS_EVIDENCE"),
    "P03": ("design_runs/run_003/outputs/p03_rx_controlled_end_to_end_pipeline_v2_replay_minimal_sample", "p03_rx_decision.json", "READINESS_EVIDENCE"),
    "C04": ("design_runs/run_003/outputs/c04_rx_complete_e01b_regression_fixture_repair", "c04_rx_decision.json", "REGRESSION_FIXTURE_EVIDENCE"),
    "P04": ("design_runs/run_003/outputs/p04_rx_controlled_real_reference_single_sample_pipeline_v2", "p04_rx_decision.json", "READINESS_EVIDENCE"),
    "P05": ("design_runs/run_003/outputs/p05_rx_four_core_pipeline_v2_regression_e02_references", "p05_rx_decision.json", "READINESS_EVIDENCE"),
    "P06": ("design_runs/run_003/outputs/p06_rx_four_core_pipeline_v2_aggregate_regression_review_pack", "p06_rx_decision.json", "NONCANONICAL_REVIEW_EVIDENCE"),
    "C05": ("design_runs/run_003/outputs/c05_rx_patch_four_core_pipeline_v2_limitations_native_component_hardening", "c05_rx_decision.json", "READINESS_EVIDENCE"),
}


PASS_PREFIXES = ("P02_PASS", "P03_PASS", "C04_PASS", "P04_PASS", "P05_PASS", "P06_PASS", "C05_PASS", "A01_PASS", "B03_PASS", "E01P_PASS", "B01_PASS", "T01_PASS", "T02_PASS", "C01_PASS", "C02B_PASS", "C03A_PASS", "C03A_RETRY_PASS")


def build_pipeline_v2_evidence_inventory(root: str | Path = ".") -> dict[str, Any]:
    base = Path(root)
    stages: dict[str, Any] = {}
    for stage, (folder, decision_file, evidence_class) in STAGE_PATHS.items():
        folder_path = base / folder
        decision_path = folder_path / decision_file
        data = _read_json(decision_path)
        decision = data.get("decision") or data.get("decision_label")
        passed = bool(decision and str(decision).startswith(PASS_PREFIXES))
        exists = decision_path.is_file()
        stages[stage] = {
            "stage": stage,
            "decision": decision,
            "output_folder": str(folder_path),
            "decision_path": str(decision_path),
            "exists": exists,
            "passed_or_limited": passed,
            "key_evidence": [str(decision_path)] if exists else [],
            "protected_artifact_status": data.get("protected_artifact_status") or _protected_status(folder_path),
            "product_pass": bool(data.get("product_pass", False)),
            "scope": _scope_for_stage(stage),
            "limitations": data.get("limitations", []),
            "evidence_class": evidence_class,
            "relevance_to_recovery_validation_bridge": _bridge_relevance(stage),
            "relevance_to_e03": _e03_relevance(stage),
            "rerun_before_recovery_validation": False,
            "blocks_recovery_validation_bridge": stage == "C05" and not passed,
        }
    return {"schema": "pipeline_v2_evidence_inventory.v1", "stages": stages, "stage_count": len(stages), "product_pass": False}


def collect_stage_decisions(root: str | Path = ".") -> dict[str, dict[str, Any]]:
    inventory = build_pipeline_v2_evidence_inventory(root)
    return {stage: {"decision": row.get("decision"), **_read_json(Path(row["decision_path"]))} for stage, row in inventory["stages"].items()}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _protected_status(folder: Path) -> str | None:
    post = _read_json(folder / "protected_artifact_postcheck.json")
    return post.get("status")


def _scope_for_stage(stage: str) -> str:
    if stage in {"P05", "P06", "C05"}:
        return "controlled four-core regression"
    if stage == "P04":
        return "controlled real-reference single sample"
    if stage == "P03":
        return "controlled minimal sample replay"
    return "controlled governance or pipeline evidence"


def _bridge_relevance(stage: str) -> str:
    return "required" if stage in {"P03", "C04", "P04", "P05", "P06", "C05"} else "supporting"


def _e03_relevance(stage: str) -> str:
    return "prerequisite evidence only; does not start E03"
