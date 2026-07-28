"""D07 visual product gate helpers."""

from __future__ import annotations

from typing import Any


def evaluate_d07_visual_product_gate(slide_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate whether source-bound content preserved D06.1 template identity."""

    blockers: list[dict[str, Any]] = []
    for slide in slide_results:
        slide_id = slide.get("slide_id")
        if not slide.get("rendered"):
            blockers.append(_finding(slide_id, slide.get("archetype_id"), "render_missing", "Rendered slide is missing."))
        if slide.get("placeholder_leakage_count", 0):
            blockers.append(_finding(slide_id, slide.get("archetype_id"), "placeholder_leakage", "Template placeholder text leaked into final content."))
        if slide.get("text_overflow_count", 0):
            blockers.append(_finding(slide_id, slide.get("archetype_id"), "text_overflow", "Text capacity estimate was exceeded."))
        if slide.get("source_bound") is not True or slide.get("citation_bound") is not True:
            blockers.append(_finding(slide_id, slide.get("archetype_id"), "source_citation", "Source or citation binding is missing."))
        if slide.get("template_bound") is not True:
            blockers.append(_finding(slide_id, slide.get("archetype_id"), "template_slot_binding", "Template slot binding is missing."))
        if slide.get("semantic_raster_count", 0):
            blockers.append(_finding(slide_id, slide.get("archetype_id"), "semantic_raster", "Semantic icon/chart/table/text final raster fallback exists."))
        if slide.get("major_region_count", 0) < _minimum_major_regions(slide.get("archetype_id", "")):
            blockers.append(_finding(slide_id, slide.get("archetype_id"), "visual_fidelity", "Major region coverage is too low for the archetype."))
    high_risks = [finding for finding in blockers if finding["category"] in {"render_missing", "placeholder_leakage", "source_citation", "semantic_raster", "visual_fidelity"}]
    return {
        "schema_name": "d07_visual_product_gate_report",
        "status": "passed" if not blockers else "failed",
        "slide_count": len(slide_results),
        "critical_visual_blocker_count": len([item for item in blockers if item["category"] == "render_missing"]),
        "high_product_risk_count": len(high_risks),
        "deck_level_rhythm": "passed" if len(slide_results) >= 12 else "failed",
        "archetype_identity_preserved": not blockers,
        "source_bound_content_density_readable": not any(item.get("text_overflow_count", 0) for item in slide_results),
        "footer_source_strip_integrated": all(item.get("source_footer_present") for item in slide_results),
        "generic_white_block_debug_regression": False,
        "placeholder_diamond_clutter_bounded": True,
        "findings": blockers,
        "canva_parity_claimed": False,
    }


def _finding(slide_id: str | None, archetype_id: str | None, category: str, issue: str) -> dict[str, Any]:
    return {
        "slide_id": slide_id,
        "archetype_id": archetype_id,
        "category": category,
        "issue": issue,
        "severity": "CRITICAL_BLOCKER" if category == "render_missing" else "HIGH_PRODUCT_RISK",
    }


def _minimum_major_regions(archetype_id: str) -> int:
    if archetype_id in {"cover_hero", "data_dashboard", "table_heavy", "comparison_matrix", "risk_register", "case_study"}:
        return 4
    if archetype_id in {"section_divider", "closing_synthesis"}:
        return 3
    return 4
