from __future__ import annotations

from typing import Any

from .controlled_sample import CONTROLLED_SAMPLE_ID, build_controlled_sample_artifact_map
from .gate_rollup import build_gate_rollup
from .hash_lineage import build_hash_lineage


def build_replay_plan() -> dict[str, Any]:
    return {
        "schema": "controlled_sample_replay_plan.v1",
        "sample_id": CONTROLLED_SAMPLE_ID,
        "mode": "IMPORT_EXISTING",
        "execute_compile": False,
        "execute_render": False,
        "import_existing_artifacts": True,
        "validations": ["hashes", "gate_statuses", "dag_completeness", "boundaries"],
        "product_pass": False,
    }


def replay_existing() -> dict[str, Any]:
    artifact_map = build_controlled_sample_artifact_map()
    lineage = build_hash_lineage()
    gate_rollup = build_gate_rollup()
    missing = [item["artifact_id"] for item in artifact_map["artifacts"] if item.get("required", True) and not item["exists"]]
    hash_failures = lineage.get("failures", [])
    gate_failures = [row["stage"] for row in gate_rollup["gates"] if not row["pass_status"]]
    if missing:
        status = "REPLAY_IMPORT_FAIL_MISSING_ARTIFACT"
    elif hash_failures:
        status = "REPLAY_IMPORT_FAIL_HASH_MISMATCH"
    elif gate_failures:
        status = "REPLAY_IMPORT_FAIL_GATE_STATUS"
    else:
        status = "REPLAY_IMPORT_PASS_WITH_LIMITATIONS"
    return {
        "schema": "controlled_sample_import_existing_replay_report.v1",
        "sample_id": CONTROLLED_SAMPLE_ID,
        "mode": "IMPORT_EXISTING",
        "imported_stages": [row["stage"] for row in gate_rollup["gates"]],
        "imported_artifacts": [item["artifact_id"] for item in artifact_map["artifacts"] if item["exists"]],
        "hash_checks": {"lineage_valid": lineage["lineage_valid"], "failures": hash_failures},
        "gate_checks": {"gate_rollup_status": gate_rollup["gate_rollup_status"], "failures": gate_failures},
        "missing_optional_artifacts": [],
        "limitations": ["controlled minimal sample only", "not reference-driven", "E01B fixture debt remains", "text overflow strictness remains limited", "minimal_ooxml backend scope"],
        "blocked_claims": ["product_pass", "E03", "E04", "D08", "C11", "bulk", "canonical_promotion"],
        "replay_status": status,
        "product_pass": False,
    }
