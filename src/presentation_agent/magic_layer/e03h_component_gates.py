"""E03H component gates."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e02h_component_gates import (
    build_e02h_micro_component_gate_report,
    build_e02h_micro_component_report,
    build_e02h_reference_component_gate,
    build_e02h_semantic_icon_report,
    component_coverage_matrix_markdown,
)


def build_e03h_semantic_icon_report(payload: dict[str, Any]) -> dict[str, Any]:
    return build_e02h_semantic_icon_report(payload)


def build_e03h_micro_component_report(payload: dict[str, Any]) -> dict[str, Any]:
    return build_e02h_micro_component_report(payload)


def build_e03h_micro_component_gate_report(payload: dict[str, Any]) -> dict[str, Any]:
    return build_e02h_micro_component_gate_report(payload)


def build_e03h_reference_component_gate(payload: dict[str, Any]) -> dict[str, Any]:
    gate = build_e02h_reference_component_gate(payload)
    reference_id = payload["reference_id"]
    if reference_id == "comparison_matrix_hybrid":
        native_table = payload["semantic_native_layer_manifest"]["native_table_count"] >= 1
        gate["native_table_count"] = payload["semantic_native_layer_manifest"]["native_table_count"]
        gate["native_table_decision"] = "passed" if native_table else "failed"
        gate["native_chart_table_decision"] = gate["native_table_decision"]
        gate["status"] = "passed" if native_table else "failed"
    if reference_id in {"methodology_framework_layered", "timeline_roadmap_hybrid"}:
        connectors = [node for node in payload["object_graph_v2"]["nodes"] if node["object_type"] == "connector" and node["editability_target"] in {"ppt_connector", "native_vector"}]
        gate["connector_vector_count"] = len(connectors)
        gate["status"] = "passed" if len(connectors) >= 3 else "failed"
    return gate


def build_e03h_component_coverage_matrix(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    coverage = {}
    for payload in payloads:
        gate = build_e03h_reference_component_gate(payload)
        reference_id = payload["reference_id"]
        coverage[reference_id] = {
            "semantic_text": payload["semantic_native_layer_manifest"]["editable_text_layer_count"] > 0,
            "semantic_icons_vector": build_e03h_semantic_icon_report(payload)["status"] == "passed",
            "vector_connectors": gate.get("connector_vector_count", 0) >= 3 if reference_id in {"process_workflow_infographic", "methodology_framework_layered", "timeline_roadmap_hybrid"} else True,
            "native_chart": gate.get("native_chart_count", 0) >= 1 if reference_id == "data_dashboard_hybrid" else True,
            "native_table": gate.get("native_table_count", 0) >= 1 if reference_id in {"table_matrix_hybrid", "comparison_matrix_hybrid"} else True,
            "component_gate_status": gate["status"],
        }
    passed = all(all(values.values()) for values in coverage.values())
    return {"schema_name": "e03h_component_coverage_matrix", "status": "passed" if passed else "failed", "coverage": coverage, "canva_parity_claimed": False}


__all__ = [
    "build_e03h_semantic_icon_report",
    "build_e03h_micro_component_report",
    "build_e03h_micro_component_gate_report",
    "build_e03h_reference_component_gate",
    "build_e03h_component_coverage_matrix",
    "component_coverage_matrix_markdown",
]
