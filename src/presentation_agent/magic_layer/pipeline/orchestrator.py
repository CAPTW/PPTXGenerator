from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifact_contract import build_artifact_contract
from .controlled_sample import CONTROLLED_SAMPLE_ID, build_controlled_sample_artifact_map
from .gate_contract import build_gate_contract
from .gate_rollup import build_gate_rollup
from .hash_lineage import build_hash_lineage
from .mode_policy import build_pipeline_mode_policy, check_mode_allowed
from .pipeline_boundary import build_boundary_report, build_scaleout_lock_recheck
from .pipeline_context import build_pipeline_context
from .pipeline_dag import build_pipeline_dag, validate_pipeline_dag
from .pipeline_state import build_pipeline_state
from .replay_existing import build_replay_plan, replay_existing
from .stage_registry import build_stage_registry


def build_orchestrator_spec() -> dict[str, Any]:
    return {
        "schema": "pipeline_v2_orchestrator_spec.v1",
        "orchestrator_id": "magic_layer_pipeline_v2_controlled_sample",
        "default_sample": CONTROLLED_SAMPLE_ID,
        "allowed_modes": ["IMPORT_EXISTING", "DRY_RUN_ONLY"],
        "forbidden_in_p02": ["compile", "render", "reference_generation", "source_bound", "scaleout", "canonical_promotion"],
        "commands": ["status", "plan", "replay-existing", "validate-manifest", "gate-rollup", "stage-check"],
        "product_pass": False,
    }


def pipeline_status() -> dict[str, Any]:
    registry = build_stage_registry()
    dag = build_pipeline_dag()
    replay = replay_existing()
    return {
        "schema": "pipeline_status.v1",
        "sample_id": CONTROLLED_SAMPLE_ID,
        "stage_count": registry["stage_count"],
        "dag_valid": validate_pipeline_dag(dag, registry)["pass"],
        "replay_status": replay["replay_status"],
        "product_pass": False,
        "scaleout_allowed": False,
    }


def pipeline_plan(sample: str = CONTROLLED_SAMPLE_ID, mode: str = "import-existing") -> dict[str, Any]:
    mode_check = check_mode_allowed(mode)
    return {
        "schema": "pipeline_plan.v1",
        "sample_id": sample,
        "mode_check": mode_check,
        "replay_plan": build_replay_plan() if mode_check["allowed"] else None,
        "blocked": not mode_check["allowed"],
        "product_pass": False,
    }


def validate_manifest(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.is_file():
        return {"schema": "pipeline_manifest_validation.v1", "pass": False, "failures": ["manifest missing"], "product_pass": False}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"schema": "pipeline_manifest_validation.v1", "pass": False, "failures": [repr(exc)], "product_pass": False}
    failures = []
    if data.get("product_pass") is not False:
        failures.append("product_pass must be false")
    return {"schema": "pipeline_manifest_validation.v1", "pass": not failures, "failures": failures, "manifest_schema": data.get("schema"), "product_pass": False}


def stage_check(stage: str) -> dict[str, Any]:
    upper = stage.upper()
    if upper in {"E03", "E04", "D08", "C11", "BULK", "CANONICAL_PROMOTION"}:
        return {"schema": "pipeline_stage_check.v1", "stage": upper, "allowed": False, "status": "BLOCKED_BY_SCALEOUT_LOCK", "product_pass": False}
    return {"schema": "pipeline_stage_check.v1", "stage": upper, "allowed": upper in {s["stage_id"] for s in build_stage_registry()["stages"]}, "status": "IMPORT_ONLY", "product_pass": False}


def build_full_orchestrator_bundle() -> dict[str, Any]:
    registry = build_stage_registry()
    dag = build_pipeline_dag()
    return {
        "spec": build_orchestrator_spec(),
        "mode_policy": build_pipeline_mode_policy(),
        "stage_registry": registry,
        "dag": dag,
        "dag_validation": validate_pipeline_dag(dag, registry),
        "artifact_contract": build_artifact_contract(),
        "gate_contract": build_gate_contract(),
        "state": build_pipeline_state(),
        "context": build_pipeline_context(),
        "artifact_map": build_controlled_sample_artifact_map(),
        "hash_lineage": build_hash_lineage(),
        "gate_rollup": build_gate_rollup(),
        "replay_plan": build_replay_plan(),
        "replay_report": replay_existing(),
        "boundary": build_boundary_report(),
        "scaleout": build_scaleout_lock_recheck(),
    }
