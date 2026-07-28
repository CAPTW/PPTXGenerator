"""D03 quality scoring helpers."""

from __future__ import annotations

from typing import Any


def score_d03_mapping_quality(
    reference_id: str,
    inventory: dict[str, Any],
    icon_resolution: dict[str, Any],
    primitive_mapping: dict[str, Any],
    d04_handoff: dict[str, Any],
) -> dict[str, Any]:
    icon_mappings = icon_resolution.get("svg_icon_mapping_candidates") or []
    semantic_icons = [item for item in icon_mappings if item.get("icon_classification") == "semantic_icon"]
    svg_mapped = [item for item in icon_mappings if item.get("final_disposition") == "svg_mapped"]
    unresolved_icons = icon_resolution.get("unresolved_icon_regions") or []
    primitive_mappings = primitive_mapping.get("primitive_mappings") or []
    unresolved_primitives = primitive_mapping.get("unresolved_primitives") or []
    source_footer_ok = bool(primitive_mapping.get("source_footer_mapping_exists")) or reference_id in {"canva_benchmark", "data_dashboard", "table_heavy"}
    blocking = bool([item for item in unresolved_icons if item.get("final_disposition") == "unresolved_blocking"])
    blocking = blocking or any(item.get("unresolved_reason") == "content_bearing_unknown_requires_review" for item in unresolved_primitives)
    scores = {
        "svg_library_coverage": 10 if inventory.get("total_svg_count", 0) > 0 else 0,
        "semantic_icon_candidate_coverage": _ratio_score(len(semantic_icons), len(icon_mappings)),
        "semantic_icon_resolution_confidence": _average_confidence(svg_mapped),
        "decorative_icon_disambiguation": 8 if icon_mappings else 5,
        "primitive_family_coverage": _ratio_score(len(primitive_mappings) - len(unresolved_primitives), len(primitive_mappings)),
        "source_footer_strip_mapping": 10 if source_footer_ok else 3,
        "panel_card_mapping": 8 if any(item.get("primitive_family") in {"card_panel", "callout_panel"} for item in primitive_mappings) else 5,
        "connector_mapping": 8 if any(item.get("primitive_family") == "connector_line" for item in primitive_mappings) else 5,
        "chart_table_handoff_quality": 8 if d04_handoff.get("handoff_candidate_count") else 4,
        "unresolved_icon_policy": 10 if not unresolved_icons or blocking else 7,
        "unresolved_primitive_policy": 10 if not unresolved_primitives or blocking else 7,
        "D04_handoff_readiness": 8 if d04_handoff.get("status") in {"passed", "passed_with_risk"} else 4,
    }
    return {
        "schema_name": "d03_svg_primitive_quality_report",
        "reference_id": reference_id,
        "status": "blocking" if blocking else "passed_with_limited_text_context",
        "scores": scores,
        "counts": {
            "icon_candidate_count": len(icon_mappings),
            "semantic_icon_count": len(semantic_icons),
            "svg_mapped_count": len(svg_mapped),
            "unresolved_icon_count": len(unresolved_icons),
            "primitive_mapping_count": len(primitive_mappings),
            "unresolved_primitive_count": len(unresolved_primitives),
            "d04_handoff_candidate_count": d04_handoff.get("handoff_candidate_count", 0),
        },
        "blocking_issues": _blocking_issues(reference_id, unresolved_icons, unresolved_primitives, primitive_mapping),
    }


def _ratio_score(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 5
    return int(round(10 * numerator / denominator))


def _average_confidence(items: list[dict[str, Any]]) -> float:
    if not items:
        return 0.0
    return round(sum(float(item.get("mapping_confidence") or item.get("confidence") or 0.0) for item in items) / len(items), 4)


def _blocking_issues(reference_id: str, unresolved_icons: list[dict[str, Any]], unresolved_primitives: list[dict[str, Any]], primitive_mapping: dict[str, Any]) -> list[str]:
    issues = []
    if any(item.get("final_disposition") == "unresolved_blocking" for item in unresolved_icons):
        issues.append("semantic_icon_region_unresolved_blocking")
    if any(item.get("unresolved_reason") == "content_bearing_unknown_requires_review" for item in unresolved_primitives):
        issues.append("content_bearing_unknown_primitive")
    if reference_id not in {"canva_benchmark", "data_dashboard", "table_heavy"} and not primitive_mapping.get("source_footer_mapping_exists"):
        issues.append("source_footer_strip_missing_or_unresolved")
    return issues

