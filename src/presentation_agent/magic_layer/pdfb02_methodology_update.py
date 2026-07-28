"""Methodology update derived from PDFB02."""

from __future__ import annotations

from typing import Any


def build_pdfb02_methodology_update(best_strategy: str) -> dict[str, Any]:
    return {
        "schema_name": "canva_plus_conversion_methodology_update_v2",
        "status": "passed" if best_strategy == "hybrid_backplate_semantic_native" else "patch_required",
        "default_strategy_for_e01h_v2": best_strategy,
        "when_to_use_hybrid_backplate_semantic_native": "Use as default when semantic text/icons/tables/charts can be separated from bounded nonsemantic visual fields.",
        "when_to_use_clone_semantic_substitution": "Use only after scaffold/duplicate chrome detection and cleanup passes.",
        "allowed_visual_backplates": ["bounded nonsemantic raster texture", "hero/photo field", "subtle depth layer", "decorative/vector ornament"],
        "cloned_layers_to_drop": ["placeholder boxes", "debug bounding boxes", "duplicate component borders", "table grids", "chart frames", "footer/source scaffolds"],
        "pdf_extraction_informs_image_conversion": [
            "seed text zones and reading order before backplate planning",
            "use vector primitive clusters to identify connectors and table grids",
            "use extracted image boxes as candidate bounded backplates",
            "use font size and bbox hierarchy to classify semantic slots",
        ],
        "qa_gates_for_e01h_v2": ["semantic raster blocker", "full-slide raster blocker", "duplicate chrome detector", "scaffold detector", "PDF/image object truth scorer", "SVG provenance checker"],
        "deprecated_e04h_bp_assumptions": ["transfer coverage proves quality", "media count proves hybrid richness", "source-bound deck pass proves Magic Layer conversion"],
        "metrics_replacing_transfer_coverage": ["balanced visual/editability score", "semantic raster violations", "PDF object signal match", "useful backplate coverage", "duplicate chrome count", "scaffold count"],
        "forbidden_or_limited_strategies": ["full-slide reference background", "raster_page_baseline as product output", "clone_semantic_substitution without cleanup"],
        "canva_parity_claimed": False,
    }


def build_failure_mode_taxonomy_v2() -> dict[str, Any]:
    return {
        "schema_name": "failure_mode_taxonomy_v2",
        "status": "passed",
        "failure_modes": [
            "visual richness collapse",
            "semantic raster fallback",
            "text lift failure",
            "icon provenance failure",
            "native table/chart failure",
            "duplicate chrome",
            "scaffold clone",
            "reading order failure",
            "table structure failure",
            "chart region misclassification",
            "overfitting to dark/cyan design language",
            "score metric false positive",
        ],
        "canva_parity_claimed": False,
    }
