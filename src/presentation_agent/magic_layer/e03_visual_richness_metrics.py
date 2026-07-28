"""Visual richness metrics for E03-VQ."""

from __future__ import annotations

from typing import Any


def calculate_visual_richness_score(metrics: dict[str, Any]) -> dict[str, Any]:
    shape_count = int(metrics.get("shape_count", 0))
    text_count = int(metrics.get("text_count", 0))
    media_count = int(metrics.get("media_count", 0))
    chart_count = int(metrics.get("chart_count", 0))
    table_count = int(metrics.get("table_count", 0))
    connector_count = int(metrics.get("connector_vector_count", metrics.get("connector_count", 0)))
    motif_count = int(metrics.get("decorative_motif_count", 0))
    accent_count = int(metrics.get("accent_shape_count", 0))
    component_count = int(metrics.get("archetype_component_count", 0))
    placeholder_ratio = float(metrics.get("placeholder_ratio", metrics.get("placeholder_text_ratio", 0.0)))

    breakdown = {
        "distinct_layout_composition": min(0.16, shape_count * 0.008),
        "visual_hierarchy_depth": min(0.14, max(text_count, 1) * 0.012),
        "decorative_motif_system": min(0.16, motif_count * 0.055 + connector_count * 0.018),
        "bounded_visual_field_usage": min(0.12, (media_count + int(metrics.get("hero_visual_field_count", 0))) * 0.08),
        "accent_usage": min(0.12, accent_count * 0.018),
        "card_panel_style_richness": min(0.10, int(metrics.get("card_panel_count", 0)) * 0.018),
        "footer_source_system_quality": 0.06 if metrics.get("has_footer_system") else 0.0,
        "archetype_specific_component_presence": min(0.18, component_count * 0.04 + chart_count * 0.08 + table_count * 0.08),
    }
    penalties: list[str] = []
    penalty_value = 0.0
    if placeholder_ratio >= 0.72:
        penalties.append("placeholder_overdominance")
        penalty_value += 0.18
    if motif_count == 0 and connector_count == 0:
        penalties.append("decorative_motif_absent")
        penalty_value += 0.10
    if media_count == 0 and int(metrics.get("hero_visual_field_count", 0)) == 0 and metrics.get("requires_visual_field"):
        penalties.append("required_visual_field_unused")
        penalty_value += 0.10
    if component_count <= 1:
        penalties.append("archetype_specific_component_sparse")
        penalty_value += 0.06
    score = max(0.0, min(1.0, sum(breakdown.values()) - penalty_value))
    return {
        "archetype_id": metrics.get("archetype_id"),
        "score": round(score, 4),
        "breakdown": {key: round(value, 4) for key, value in breakdown.items()},
        "penalties": penalties,
    }


def build_visual_richness_score_report(
    slide_records: list[dict[str, Any]],
    *,
    average_threshold: float = 0.60,
    core_threshold: float = 0.48,
) -> dict[str, Any]:
    slide_scores = [calculate_visual_richness_score(record) for record in slide_records]
    average = round(sum(score["score"] for score in slide_scores) / len(slide_scores), 4) if slide_scores else 0.0
    failures: list[str] = []
    if average < average_threshold:
        failures.append("average_visual_richness_below_threshold")
    for score in slide_scores:
        if score["score"] < core_threshold:
            failures.append(f"{score['archetype_id']}_visual_richness_below_threshold")
        if "required_visual_field_unused" in score["penalties"]:
            failures.append(f"{score['archetype_id']}_required_visual_field_unused")
    return {
        "schema_name": "visual_richness_score_report",
        "status": "passed" if not failures else "failed",
        "average_visual_richness_score": average,
        "average_threshold": average_threshold,
        "core_threshold": core_threshold,
        "slide_scores": slide_scores,
        "failures": sorted(set(failures)),
        "canva_parity_claimed": False,
    }
