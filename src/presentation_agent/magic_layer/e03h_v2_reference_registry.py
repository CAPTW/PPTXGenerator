"""Reference registry checks for E03H-V2."""

from __future__ import annotations

from typing import Any


CORE_REFERENCE_IDS = [
    "maritime_checklist_hero",
    "process_workflow_infographic",
    "data_dashboard_hybrid",
    "table_matrix_hybrid",
    "cover_hero_photo_editorial",
    "standard_content_card_cluster",
    "evidence_stack_visual",
    "comparison_matrix_hybrid",
    "methodology_framework_layered",
    "timeline_roadmap_hybrid",
    "visual_toc_navigation",
    "photo_caption_grid_hybrid",
]


def build_e03h_v2_reference_registry(manifest: dict[str, Any]) -> dict[str, Any]:
    refs = manifest.get("references", [])
    ids = {ref.get("reference_id") for ref in refs}
    missing = [ref_id for ref_id in CORE_REFERENCE_IDS if ref_id not in ids]
    non_dark = sum(1 for ref in refs if ref.get("background_mode") != "dark")
    raster = sum(1 for ref in refs if ref.get("has_raster_backplate"))
    dense = sum(1 for ref in refs if ref.get("dense_vector") or ref.get("requires_chart") or ref.get("requires_table"))
    table = sum(1 for ref in refs if ref.get("requires_table"))
    chart = sum(1 for ref in refs if ref.get("requires_chart"))
    icons = sum(1 for ref in refs if ref.get("semantic_icon_required"))
    passed = not missing and len(refs) >= 12 and non_dark >= 3 and raster >= 3 and dense >= 3 and table >= 2 and chart >= 1 and icons >= 4
    return {
        "schema_name": "e03h_v2_reference_registry",
        "status": "passed" if passed else "failed",
        "reference_count": len(refs),
        "core_reference_count": len([ref for ref in refs if ref.get("is_core")]),
        "missing_core_references": missing,
        "non_dark_reference_count": non_dark,
        "raster_visual_backplate_reference_count": raster,
        "dense_vector_table_chart_reference_count": dense,
        "native_table_reference_count": table,
        "native_chart_reference_count": chart,
        "semantic_svg_icon_reference_count": icons,
        "references": refs,
        "canva_parity_claimed": False,
    }
