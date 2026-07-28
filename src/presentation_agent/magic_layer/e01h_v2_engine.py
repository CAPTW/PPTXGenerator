"""E01H-V2 policy and engine-level helpers."""

from __future__ import annotations

from typing import Any


def build_engine_policy(methodology_update: dict[str, Any]) -> dict[str, Any]:
    default_strategy = methodology_update.get("default_strategy_for_e01h_v2") or "hybrid_backplate_semantic_native"
    return {
        "schema_name": "e01h_v2_engine_policy",
        "status": "passed" if default_strategy == "hybrid_backplate_semantic_native" else "failed",
        "default_strategy": default_strategy,
        "raster_page_baseline": "benchmark_only_forbidden_in_product",
        "text_lift_overlay_baseline": "fallback_only_not_product_default",
        "native_shape_reconstruction_baseline": "allowed_only_when_visual_richness_low_or_no_backplate_exists",
        "clone_semantic_substitution": {
            "default": False,
            "allowed_only_when_clone_guard_passes": True,
            "restricted_strategy": True,
        },
        "pdf_object_signals_used_as_hints": True,
        "style_preservation_mandatory": True,
        "object_count_is_quality_metric": False,
        "allowed_visual_backplates": methodology_update.get(
            "allowed_visual_backplates",
            ["bounded nonsemantic raster texture", "hero/photo field", "subtle depth layer", "decorative/vector ornament"],
        ),
        "cloned_layers_to_drop": methodology_update.get(
            "cloned_layers_to_drop",
            ["placeholder boxes", "debug bounding boxes", "duplicate component borders", "table grids", "chart frames", "footer/source scaffolds"],
        ),
        "forbidden_product_strategies": ["raster_page_baseline", "full_slide_reference_background", "screenshot_slide"],
        "semantic_raster_forbidden": True,
        "canva_parity_claimed": False,
    }
