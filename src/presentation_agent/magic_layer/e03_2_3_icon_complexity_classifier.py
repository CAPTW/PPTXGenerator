"""Classify cleaned icon candidates by vectorization complexity."""

from __future__ import annotations

from collections import Counter
from typing import Any


COMPLEX_ROLES = {"evidence_trace", "risk_status", "decision_diamond", "network", "process_node", "timeline", "milestone_flag", "recommendation", "table", "chart_bar", "pie_chart"}
MEDIUM_ROLES = {"shield", "database", "document", "note", "scale", "warning", "calendar", "user", "book"}


def classify_icon_complexity(strict_report: dict[str, Any]) -> dict[str, Any]:
    icons = []
    for row in strict_report.get("accepted_or_review_icons", []):
        metrics = row.get("hygiene_metrics_v2", row.get("hygiene_metrics", {}))
        complexity = _class_for(row, metrics)
        icons.append(
            {
                **row,
                "component_count": metrics.get("component_count", 0),
                "contour_count": metrics.get("component_count", 0),
                "enclosed_shape_count": max(0, int(metrics.get("closed_contour_count", 0))),
                "stroke_density": metrics.get("foreground_area_ratio", 0.0),
                "edge_density": metrics.get("edge_density", 0.0),
                "number_of_disconnected_parts": metrics.get("component_count", 0),
                "presence_of_container": row.get("container_type") in {"circle_badge", "card_icon_well"},
                "text_contamination_score": metrics.get("text_likeness", 0.0),
                "crop_occlusion_score": 0.0,
                "library_match_score": row.get("shape_similarity", 0.0),
                "local_trace_quality_score": 0.0,
                "complexity_class": complexity,
                "requires_complex_vectorization": complexity in {"MEDIUM_MULTI_STROKE", "COMPLEX_MULTI_COMPONENT", "COMPLEX_CONTAINER_GLYPH", "CONTAMINATED_REVIEW_REQUIRED"},
            }
        )
    counts = Counter(icon["complexity_class"] for icon in icons)
    complex_count = sum(counts.get(key, 0) for key in ("COMPLEX_MULTI_COMPONENT", "COMPLEX_CONTAINER_GLYPH", "CONTAMINATED_REVIEW_REQUIRED"))
    return {
        "schema_name": "complex_icon_complexity_report",
        "status": "passed",
        "icon_count": len(icons),
        "class_counts": dict(sorted(counts.items())),
        "complex_icon_count": complex_count,
        "medium_icon_count": counts.get("MEDIUM_MULTI_STROKE", 0),
        "icons": icons,
    }


def build_complex_icon_cluster_manifest(complexity_report: dict[str, Any]) -> dict[str, Any]:
    clusters = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for icon in complexity_report.get("icons", []):
        grouped.setdefault(icon["likely_role"], []).append(icon)
    for idx, (role, members) in enumerate(sorted(grouped.items()), start=1):
        priority = "P0_REQUIRED_SEMANTIC" if any(str(member.get("priority", "")).startswith("P0") for member in members) else "P1_HIGH_REUSE"
        classes = sorted({member["complexity_class"] for member in members})
        clusters.append(
            {
                "cluster_id": f"complex_cluster_{idx:03d}_{role}",
                "likely_role": role,
                "priority": priority,
                "member_count": len(members),
                "member_icon_ids": [member["icon_id"] for member in members],
                "complexity_classes": classes,
                "requires_vectorization": any(member["requires_complex_vectorization"] for member in members),
                "representative_icon": members[0],
            }
        )
    return {"schema_name": "complex_icon_cluster_manifest", "status": "passed", "cluster_count": len(clusters), "clusters": clusters}


def _class_for(row: dict[str, Any], metrics: dict[str, Any]) -> str:
    role = row.get("likely_role")
    components = int(metrics.get("component_count", 0))
    text = float(metrics.get("text_likeness", 0.0))
    if text > 0.7:
        return "CONTAMINATED_REVIEW_REQUIRED"
    if role in COMPLEX_ROLES or components > 4:
        return "COMPLEX_MULTI_COMPONENT"
    if role in MEDIUM_ROLES or components > 2 or float(metrics.get("edge_density", 0.0)) > 0.22:
        return "MEDIUM_MULTI_STROKE"
    if float(metrics.get("foreground_area_ratio", 0.0)) > 0.25:
        return "SIMPLE_FILLED"
    return "SIMPLE_MONOLINE"
