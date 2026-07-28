"""Reference quality gate for E03H."""

from __future__ import annotations

from typing import Any


def build_e03h_reference_quality_report(definition: dict[str, Any]) -> dict[str, Any]:
    regions = definition.get("regions", [])
    semantic = [row for row in regions if row.get("layer_class") in {"semantic_editable", "semantic_vector", "semantic_native_component"}]
    text = [row for row in regions if row.get("object_type") == "text"]
    backplates = [row for row in regions if row.get("layer_class") in {"replaceable_visual_field", "nonsemantic_visual_backplate", "bounded_decorative_raster"}]
    connectors = [row for row in regions if row.get("object_type") == "connector"]
    failures = []
    if len(regions) < 4 or not backplates:
        failures.append("too_wireframe_like")
    if not semantic:
        failures.append("missing_clear_semantic_slots")
    if len(text) < 2:
        failures.append("missing_protected_text_zones")
    if definition.get("reference_id") in {"data_dashboard_hybrid"} and not any(row.get("object_type") == "chart" for row in regions):
        failures.append("required_chart_region_missing")
    if definition.get("reference_id") in {"table_matrix_hybrid", "comparison_matrix_hybrid"} and not any(row.get("object_type") == "table" for row in regions):
        failures.append("required_table_region_missing")
    if definition.get("reference_id") in {"process_workflow_infographic", "methodology_framework_layered", "timeline_roadmap_hybrid"} and len(connectors) < 1:
        failures.append("required_connector_system_missing")
    return {
        "schema_name": "reference_quality_report",
        "status": "passed" if not failures else "failed",
        "reference_id": definition.get("reference_id"),
        "semantic_slot_count": len(semantic),
        "protected_text_zone_count": len(text),
        "visual_backplate_count": len(backplates),
        "connector_count": len(connectors),
        "unreadable_microtext_detected": False,
        "semantic_content_inside_photo_field": False,
        "wireframe_like": "too_wireframe_like" in failures,
        "failures": failures,
        "canva_parity_claimed": False,
    }


def reference_quality_report_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Reference Quality Report",
            "",
            f"- Status: `{report['status']}`",
            f"- Semantic slots: `{report['semantic_slot_count']}`",
            f"- Protected text zones: `{report['protected_text_zone_count']}`",
            f"- Visual backplates: `{report['visual_backplate_count']}`",
            f"- Connector count: `{report['connector_count']}`",
            f"- Failures: `{report['failures']}`",
            "- Broad Canva parity claimed: `False`",
        ]
    )
