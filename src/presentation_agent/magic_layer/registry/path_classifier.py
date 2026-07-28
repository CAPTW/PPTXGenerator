from __future__ import annotations

from pathlib import Path
from typing import Any


PROTECTED_ARTIFACTS = {
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
}


def normalize_path(path: str | Path) -> str:
    return str(path).replace("\\", "/").strip()


def _state_list(repo_state: dict[str, Any], key: str) -> set[str]:
    values = repo_state.get(key, [])
    if isinstance(values, dict):
        values = values.get("paths", [])
    return {normalize_path(value).rstrip("/") for value in values}


def is_protected_artifact(path: str | Path) -> bool:
    return normalize_path(path).rstrip("/") in PROTECTED_ARTIFACTS


def is_quarantined_path(path: str | Path, repo_state: dict[str, Any]) -> bool:
    normalized = normalize_path(path)
    quarantine = normalize_path(repo_state.get("quarantine_folder", "")).rstrip("/")
    if quarantine and normalized.lower().startswith(quarantine.lower() + "/"):
        return True
    return normalized.startswith("_local_quarantine/") or "__quarantine_pre_a01_" in normalized


def is_manual_review_path(path: str | Path, repo_state: dict[str, Any]) -> bool:
    normalized = normalize_path(path).rstrip("/")
    return normalized in _state_list(repo_state, "manual_review_paths")


def is_active_fixture_path(path: str | Path) -> bool:
    normalized = normalize_path(path)
    return normalized.startswith("design_runs/run_003/fixtures/")


def is_active_core_path(path: str | Path) -> bool:
    normalized = normalize_path(path)
    if normalized in {"package.json", "package-lock.json", "pyproject.toml", "pytest.ini", "setup.cfg", "tsconfig.json", "README.md", "AGENTS.md"}:
        return True
    return normalized.startswith(("src/", "scripts/", "tests/", "repo_state/"))


def classify_artifact_family(path: str | Path, repo_state: dict[str, Any]) -> str:
    normalized = normalize_path(path).rstrip("/")
    if is_quarantined_path(normalized, repo_state):
        return "GOVERNANCE_RUN_QUARANTINED"
    if is_protected_artifact(normalized):
        return "PROTECTED_CANONICAL"
    if is_manual_review_path(normalized, repo_state):
        return "MANUAL_REVIEW_UNKNOWN"
    if normalized.startswith("design_runs/run_003/fixtures/r01_failure_analysis_context/"):
        return "R01_FAILURE_ANALYSIS_CONTEXT"
    if normalized.startswith("design_runs/run_003/fixtures/e01_semantic_raster_fail/"):
        return "E01_FAIL_FIXTURE"
    if normalized.startswith("design_runs/run_003/fixtures/e01b_single_reference_pass/"):
        return "E01B_PASS_FIXTURE"
    if normalized.startswith("design_runs/run_003/fixtures/e02_4core_pass/"):
        return "E02_4CORE_PASS_FIXTURE"
    if normalized.startswith("design_runs/run_003/fixtures/canva_benchmark/"):
        return "CANVA_BENCHMARK_FIXTURE"
    if is_active_fixture_path(normalized):
        return "ACTIVE_FIXTURE"
    if is_active_core_path(normalized):
        return "ACTIVE_CORE"
    if normalized.startswith("design_runs/run_003/outputs/a01_rx_artifact_registry_claim_verification_cli/"):
        return "ACTIVE_FIXTURE"
    if normalized.startswith("design_runs/run_003/outputs/b03_rx_pptx_native_validation_cli_hardening/"):
        return "ACTIVE_FIXTURE"
    if normalized.startswith("design_runs/run_003/outputs/e01p_rx_psd_like_layer_mask_selection_protocol/"):
        return "ACTIVE_FIXTURE"
    if normalized.startswith("design_runs/run_003/outputs/b01_rx_render_review_workbench/"):
        return "ACTIVE_FIXTURE"
    if normalized.startswith("design_runs/run_003/outputs/t01_rx_template_contract_slot_schema_hardening/"):
        return "ACTIVE_FIXTURE"
    if normalized.startswith("design_runs/run_003/outputs/t02_rx_native_reconstruction_planner_editable_spec_builder/"):
        return "ACTIVE_FIXTURE"
    if normalized.startswith("design_runs/run_003/outputs/c01_rx_contract_aware_pptx_compiler_skeleton_dry_run/"):
        return "ACTIVE_FIXTURE"
    if normalized.startswith("design_runs/run_003/outputs/c02_rx_controlled_minimal_pptx_compile/"):
        return "ACTIVE_FIXTURE"
    if normalized.startswith("design_runs/run_003/outputs/c03_rx_controlled_render_b01_review_minimal_pptx/"):
        return "ACTIVE_FIXTURE"
    if normalized.startswith("design_runs/run_002/outputs/"):
        return "HISTORICAL_AUDIT_QUARANTINED"
    return "UNKNOWN_ACTIVE_FILE"
