from __future__ import annotations

from typing import Any

from .controlled_sample import build_controlled_sample_artifact_map


def build_artifact_contract() -> dict[str, Any]:
    artifact_map = build_controlled_sample_artifact_map()
    artifacts = []
    for item in artifact_map["artifacts"]:
        artifacts.append(
            {
                "artifact_id": item["artifact_id"],
                "class": item["class"],
                "path": item["path"],
                "expected_hash": item.get("expected_hash"),
                "produced_by_stage": _producer(item["artifact_id"]),
                "consumed_by_stage": _consumers(item["artifact_id"]),
                "required": item["artifact_id"] not in {"c02_original_pptx"},
                "product_evidence_scope": "controlled_minimal_sample_only",
                "product_pass_allowed": False,
                "limitations": item["limitations"],
                "validation_rule": "exists_and_hash_matches_when_expected",
                "quarantine_allowed": False,
                "manual_review_allowed": True,
            }
        )
    return {"schema": "pipeline_artifact_contract.v1", "artifacts": artifacts, "product_pass": False}


def _producer(artifact_id: str) -> str:
    if artifact_id.startswith("t02"):
        return "T02_NATIVE_RECONSTRUCTION_PLANNER"
    if artifact_id.startswith("c01"):
        return "C01_COMPILER_DRY_RUN"
    if artifact_id.startswith("c02b"):
        return "C02B_CONTROLLED_COMPATIBLE_COMPILE"
    if artifact_id == "c02_original_pptx":
        return "C02_CONTROLLED_MINIMAL_COMPILE"
    if artifact_id == "c03a_retry_render":
        return "C03A_RETRY_CONTROLLED_RENDER"
    return "B01_REVIEW_PACKET"


def _consumers(artifact_id: str) -> list[str]:
    if artifact_id == "c02b_patched_pptx":
        return ["B03_PPTX_NATIVE_VALIDATION", "C03A_RETRY_CONTROLLED_RENDER"]
    if artifact_id == "c03a_retry_render":
        return ["B01_REVIEW_PACKET"]
    return ["CLAIM_BOUNDARY_CHECK"]
