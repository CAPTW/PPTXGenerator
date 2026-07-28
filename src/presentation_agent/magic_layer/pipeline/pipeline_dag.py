from __future__ import annotations

from typing import Any

from .stage_registry import STAGE_ORDER, stage_ids


EDGES = [
    ("A01_REGISTRY_CLAIM_GUARD", "E01P_PROTOCOL_GATE"),
    ("A01_REGISTRY_CLAIM_GUARD", "T01_TEMPLATE_CONTRACT_GATE"),
    ("A01_REGISTRY_CLAIM_GUARD", "T02_NATIVE_RECONSTRUCTION_PLANNER"),
    ("A01_REGISTRY_CLAIM_GUARD", "C01_COMPILER_DRY_RUN"),
    ("A01_REGISTRY_CLAIM_GUARD", "C02B_CONTROLLED_COMPATIBLE_COMPILE"),
    ("A01_REGISTRY_CLAIM_GUARD", "B03_PPTX_NATIVE_VALIDATION"),
    ("A01_REGISTRY_CLAIM_GUARD", "C03A_RETRY_CONTROLLED_RENDER"),
    ("A01_REGISTRY_CLAIM_GUARD", "B01_REVIEW_PACKET"),
    ("E01P_PROTOCOL_GATE", "T01_TEMPLATE_CONTRACT_GATE"),
    ("T01_TEMPLATE_CONTRACT_GATE", "T02_NATIVE_RECONSTRUCTION_PLANNER"),
    ("T02_NATIVE_RECONSTRUCTION_PLANNER", "C01_COMPILER_DRY_RUN"),
    ("C01_COMPILER_DRY_RUN", "C02B_CONTROLLED_COMPATIBLE_COMPILE"),
    ("C02B_CONTROLLED_COMPATIBLE_COMPILE", "B03_PPTX_NATIVE_VALIDATION"),
    ("B03_PPTX_NATIVE_VALIDATION", "C03A_RETRY_CONTROLLED_RENDER"),
    ("C03A_RETRY_CONTROLLED_RENDER", "B01_REVIEW_PACKET"),
    ("B01_REVIEW_PACKET", "CLAIM_BOUNDARY_CHECK"),
]


def build_pipeline_dag() -> dict[str, Any]:
    return {
        "schema": "pipeline_dag.v1",
        "nodes": [{"stage_id": stage_id} for stage_id in STAGE_ORDER],
        "edges": [{"from": src, "to": dst} for src, dst in EDGES],
        "forbidden_edges": ["T02_NATIVE_RECONSTRUCTION_PLANNER->PRODUCT_PASS", "C02B_CONTROLLED_COMPATIBLE_COMPILE->PRODUCT_PASS", "C03A_RETRY_CONTROLLED_RENDER->E03", "E03->E04", "E04->D08"],
        "product_pass": False,
    }


def validate_pipeline_dag(dag: dict[str, Any], registry: dict[str, Any] | None = None) -> dict[str, Any]:
    ids = stage_ids(registry)
    edges = [(edge["from"], edge["to"]) for edge in dag.get("edges", [])]
    failures: list[str] = []
    for node in dag.get("nodes", []):
        if node.get("stage_id") not in ids:
            failures.append(f"missing stage registry entry: {node.get('stage_id')}")
    for src, dst in edges:
        if src not in ids or dst not in ids:
            failures.append(f"edge references unknown node: {src}->{dst}")
    if _has_cycle([node["stage_id"] for node in dag.get("nodes", [])], edges):
        failures.append("DAG contains a cycle")
    forbidden_targets = {"E03", "E04", "D08", "C11", "bulk", "PRODUCT_PASS"}
    for src, dst in edges:
        if dst in forbidden_targets or "PRODUCT_PASS" in dst:
            failures.append(f"forbidden edge: {src}->{dst}")
    return {"schema": "pipeline_dag_validation.v1", "pass": not failures, "failures": failures, "acyclic": not failures, "product_pass": False}


def _has_cycle(nodes: list[str], edges: list[tuple[str, str]]) -> bool:
    children: dict[str, list[str]] = {node: [] for node in nodes}
    for src, dst in edges:
        children.setdefault(src, []).append(dst)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in children.get(node, []):
            if visit(child):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in nodes)
