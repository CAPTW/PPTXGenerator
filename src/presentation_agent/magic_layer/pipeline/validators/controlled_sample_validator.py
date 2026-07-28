from __future__ import annotations

from typing import Any

from ..controlled_sample import C02B_HASH, C03A_RENDER_HASH


def validate_controlled_sample_lineage(lineage: dict[str, Any]) -> dict[str, Any]:
    hashes = {node["artifact_id"]: node.get("hash") for node in lineage.get("nodes", [])}
    failures = []
    if hashes.get("c02b_patched_pptx") != C02B_HASH:
        failures.append("C02B PPTX hash mismatch")
    if hashes.get("c03a_retry_render") != C03A_RENDER_HASH:
        failures.append("C03A retry render hash mismatch")
    render_node = next((node for node in lineage.get("nodes", []) if node.get("artifact_id") == "c03a_retry_render"), {})
    if "c02b_patched_pptx" not in render_node.get("parent_artifacts", []):
        failures.append("render parent is not C02B PPTX")
    return {"schema": "controlled_sample_lineage_validation.v1", "pass": not failures, "failures": failures, "product_pass": False}
