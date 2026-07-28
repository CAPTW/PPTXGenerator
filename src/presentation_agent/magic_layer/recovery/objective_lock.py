from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .e03_reference_registry import build_reference_registry_template


RUN_ID = "run_004"
RUN_FOLDER = Path("design_runs/run_004")
OUTPUT_FOLDER_NAME = "rv00_rx_recovery_validation_objective_lock_e03_reference_readiness_reopen_plan"


def build_objective_transition(p07_decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "objective_transition_report.v1",
        "previous_phase": "architecture_governance_rebuild_and_controlled_pipeline_v2_regression",
        "new_phase": "recovery_validation_planning",
        "product_unit": "reference image → editable PPT-native template conversion",
        "decision": "OBJECTIVE_TRANSITION_LOCKED_TO_RECOVERY_VALIDATION_PLANNING",
        "p07_decision": p07_decision.get("decision"),
        "product_pass": False,
        "direct_e03_rerun_allowed": False,
        "e03_reference_revalidation_required": True,
        "e04_allowed": False,
        "d08_allowed": False,
        "c11_bulk_allowed": False,
        "canonical_promotion_allowed": False,
    }


def build_run_manifest(p07_decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "run_manifest.v1",
        "run_id": RUN_ID,
        "objective": "recovery_validation_planning",
        "current_objective": "recovery_validation_planning",
        "inherited_from": "run_003",
        "previous_evidence_run": "run_003",
        "p07_decision": p07_decision.get("decision"),
        "product_pass": False,
        "direct_e03_rerun_allowed": False,
        "e03_reference_revalidation_required": True,
        "e04_allowed": False,
        "d08_allowed": False,
        "c11_bulk_allowed": False,
        "canonical_promotion_allowed": False,
    }


def create_run_004_scaffold(root: str | Path, p07_decision: dict[str, Any]) -> dict[str, Any]:
    root = Path(root)
    run = root / RUN_FOLDER
    output = run / "outputs" / OUTPUT_FOLDER_NAME
    paths = [
        run,
        run / "inputs/e03_rx/references",
        output,
    ]
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)

    manifest = build_run_manifest(p07_decision)
    _write_json(run / "run_manifest.json", manifest)
    _write_text(
        run / "README.md",
        "# run_004\n\nRecovery validation planning run. RV00 does not generate references, PPTX, renders, or canonical artifacts.\n",
    )
    _write_text(
        run / "inputs/e03_rx/README.md",
        "# E03 Recovery Inputs\n\nRV00 creates only the registry scaffold. RV01 must validate any references placed here.\n",
    )
    _write_text(
        run / "inputs/e03_rx/references/README.md",
        "# E03 References\n\nDo not place generated-flood, render, contact-sheet, canonical, or quarantined artifacts here.\n",
    )
    _write_json(run / "inputs/e03_rx/reference_registry.json", build_reference_registry_template())
    return {
        "schema": "run_004_scaffold_report.v1",
        "status": "RUN_004_SCAFFOLD_READY",
        "active_recovery_run_folder": str(run),
        "output_folder": str(output),
        "created_paths": [str(path) for path in paths],
        "reference_images_copied": 0,
        "pptx_generated": 0,
        "render_generated": 0,
        "product_pass": False,
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
