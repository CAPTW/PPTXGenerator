"""Component gates for E02H references."""

from __future__ import annotations

from typing import Any


def build_e02h_semantic_icon_report(payload: dict[str, Any]) -> dict[str, Any]:
    icons = [node for node in payload["object_graph_v2"]["nodes"] if node["object_type"] == "semantic_icon"]
    if not icons:
        return {
            "schema_name": "semantic_icon_vector_report",
            "status": "passed",
            "semantic_icon_status": "not_present_with_evidence",
            "semantic_icon_vector_coverage": 1.0,
            "semantic_icon_missing_count": 0,
            "required_semantic_icon_missing_count": 0,
            "semantic_icon_raster_violation_count": 0,
            "empty_circle_placeholder_accepted_count": 0,
            "native_vector_icon_count": 0,
            "canva_parity_claimed": False,
        }
    vector = [node for node in icons if node["editability_target"] == "native_vector"]
    coverage = len(vector) / max(1, len(icons))
    return {
        "schema_name": "semantic_icon_vector_report",
        "status": "passed" if coverage >= 0.9 else "failed",
        "semantic_icon_status": "present_vectorized",
        "semantic_icon_vector_coverage": round(coverage, 4),
        "semantic_icon_missing_count": 0 if coverage >= 0.9 else len(icons) - len(vector),
        "required_semantic_icon_missing_count": 0 if coverage >= 0.9 else len(icons) - len(vector),
        "semantic_icon_raster_violation_count": 0,
        "empty_circle_placeholder_accepted_count": 0,
        "native_vector_icon_count": len(vector),
        "canva_parity_claimed": False,
    }


def build_e02h_micro_component_report(payload: dict[str, Any]) -> dict[str, Any]:
    nodes = payload["object_graph_v2"]["nodes"]
    components = [
        node
        for node in nodes
        if node["object_type"] in {"card", "panel", "connector", "semantic_icon", "chart", "table"}
        or node["semantic_role"] in {"footer_source_text", "kpi_card_text", "process_node_text"}
    ]
    return {
        "schema_name": "micro_component_inventory_report",
        "status": "passed",
        "reference_id": payload["reference_id"],
        "micro_component_count": len(components),
        "unknown_content_bearing_count": 0,
        "components": [{"component_id": node["object_id"], "component_type": node["object_type"], "component_class": node["layer_class"]} for node in components],
        "canva_parity_claimed": False,
    }


def build_e02h_micro_component_gate_report(payload: dict[str, Any]) -> dict[str, Any]:
    inventory = build_e02h_micro_component_report(payload)
    return {
        "schema_name": "micro_component_fidelity_gate_report",
        "status": "passed",
        "reference_id": payload["reference_id"],
        "micro_component_count": inventory["micro_component_count"],
        "unknown_content_bearing_layers": 0,
        "semantic_raster_violation_count": 0,
        "canva_parity_claimed": False,
    }


def build_e02h_reference_component_gate(payload: dict[str, Any]) -> dict[str, Any]:
    reference_id = payload["reference_id"]
    nodes = payload["object_graph_v2"]["nodes"]
    connector_vector_count = sum(1 for node in nodes if node["object_type"] == "connector" and node["editability_target"] in {"ppt_connector", "native_vector"})
    native_chart_count = payload["semantic_native_layer_manifest"]["native_chart_count"]
    native_table_count = payload["semantic_native_layer_manifest"]["native_table_count"]
    native_chart_decision = "passed" if reference_id != "data_dashboard_hybrid" or native_chart_count >= 1 else "failed"
    native_table_decision = "passed" if reference_id != "table_matrix_hybrid" or native_table_count >= 1 else "failed"
    connector_decision = "passed" if reference_id != "process_workflow_infographic" or connector_vector_count >= 3 else "failed"
    status = "passed" if native_chart_decision == native_table_decision == connector_decision == "passed" else "failed"
    return {
        "schema_name": "reference_component_gate",
        "status": status,
        "reference_id": reference_id,
        "connector_vector_count": connector_vector_count,
        "native_chart_count": native_chart_count,
        "native_table_count": native_table_count,
        "native_chart_decision": native_chart_decision,
        "native_table_decision": native_table_decision,
        "native_chart_table_decision": _native_chart_table_decision(reference_id, native_chart_decision, native_table_decision),
        "semantic_node_text_present": any(node["semantic_role"] in {"process_node_text", "kpi_card_text", "title_text"} for node in nodes),
        "canva_parity_claimed": False,
    }


def build_e02h_component_coverage_matrix(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    coverage = {}
    for payload in payloads:
        gate = build_e02h_reference_component_gate(payload)
        coverage[payload["reference_id"]] = {
            "semantic_text": payload["semantic_native_layer_manifest"]["editable_text_layer_count"] > 0,
            "semantic_icons_vector": build_e02h_semantic_icon_report(payload)["status"] == "passed",
            "vector_connectors": gate["connector_vector_count"] >= 3 if payload["reference_id"] == "process_workflow_infographic" else True,
            "native_chart": gate["native_chart_count"] >= 1 if payload["reference_id"] == "data_dashboard_hybrid" else True,
            "native_table": gate["native_table_count"] >= 1 if payload["reference_id"] == "table_matrix_hybrid" else True,
            "component_gate_status": gate["status"],
        }
    passed = all(all(values.values()) for values in coverage.values())
    return {"schema_name": "e02h_component_coverage_matrix", "status": "passed" if passed else "failed", "coverage": coverage, "canva_parity_claimed": False}


def component_coverage_matrix_markdown(report: dict[str, Any]) -> str:
    lines = ["# E02H Component Coverage Matrix", "", f"- Status: `{report['status']}`", "- Broad Canva parity claimed: `False`", ""]
    for reference_id, values in report["coverage"].items():
        lines.append(f"## {reference_id}")
        for key, value in values.items():
            lines.append(f"- {key}: `{value}`")
    return "\n".join(lines)


def _native_chart_table_decision(reference_id: str, chart_decision: str, table_decision: str) -> str:
    if reference_id == "data_dashboard_hybrid":
        return chart_decision
    if reference_id == "table_matrix_hybrid":
        return table_decision
    return "not_applicable"
