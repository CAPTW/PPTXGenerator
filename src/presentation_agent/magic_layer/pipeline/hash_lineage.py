from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .controlled_sample import C02B_HASH, C03A_RENDER_HASH, PATHS, CONTROLLED_SAMPLE_ID


def sha256_file(path: str | Path) -> str | None:
    p = Path(path)
    if not p.is_file():
        return None
    digest = hashlib.sha256()
    with p.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_hash_lineage() -> dict[str, Any]:
    nodes = [
        _node("t02_compiler_input_bundle", [], "planned"),
        _node("c01_dry_run_report", ["t02_compiler_input_bundle"], "dry_run"),
        _node("c01_primitive_plan", ["c01_dry_run_report"], "dry_run"),
        _node("c02_original_pptx", ["c01_primitive_plan"], "superseded"),
        _node("c02b_patched_pptx", ["c01_primitive_plan"], "compiled"),
        _node("c02b_b03_report", ["c02b_patched_pptx"], "validated"),
        _node("c03a_retry_render", ["c02b_patched_pptx"], "rendered"),
        _node("c03a_retry_b01_review_packet", ["c03a_retry_render", "c02b_b03_report"], "reviewed"),
    ]
    failures = []
    hashes = {node["artifact_id"]: node.get("hash") for node in nodes}
    if hashes.get("c02b_patched_pptx") != C02B_HASH:
        failures.append("C02B PPTX hash mismatch")
    if hashes.get("c03a_retry_render") != C03A_RENDER_HASH:
        failures.append("C03A retry render hash mismatch")
    return {"schema": "controlled_sample_hash_lineage.v1", "sample_id": CONTROLLED_SAMPLE_ID, "nodes": nodes, "lineage_valid": not failures, "failures": failures, "product_pass": False}


def _node(artifact_id: str, parents: list[str], transformation_type: str) -> dict[str, Any]:
    path = PATHS.get(artifact_id)
    return {
        "artifact_id": artifact_id,
        "path": str(path) if path else None,
        "hash": sha256_file(path) if path else None,
        "parent_artifacts": parents,
        "child_artifacts": [],
        "transformation_stage": _stage_for(artifact_id),
        "transformation_type": transformation_type,
        "product_evidence_scope": "controlled_minimal_sample_only",
        "limitations": ["not_product_pass", "not_reference_fidelity"],
    }


def _stage_for(artifact_id: str) -> str:
    if artifact_id.startswith("t02"):
        return "T02_NATIVE_RECONSTRUCTION_PLANNER"
    if artifact_id.startswith("c01"):
        return "C01_COMPILER_DRY_RUN"
    if artifact_id.startswith("c02b"):
        return "C02B_CONTROLLED_COMPATIBLE_COMPILE" if artifact_id.endswith("pptx") else "B03_PPTX_NATIVE_VALIDATION"
    if artifact_id.startswith("c03a"):
        return "C03A_RETRY_CONTROLLED_RENDER" if "render" in artifact_id else "B01_REVIEW_PACKET"
    return "C02_CONTROLLED_MINIMAL_COMPILE"
