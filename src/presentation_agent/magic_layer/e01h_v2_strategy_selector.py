"""Select E01H-V2 conversion strategy from engine policy."""

from __future__ import annotations

from typing import Any


def select_conversion_strategy(policy: dict[str, Any], case_meta: dict[str, Any]) -> dict[str, Any]:
    clone_guard_passed = bool(case_meta.get("clone_guard_passed", False))
    clone_allowed = clone_guard_passed and bool(case_meta.get("valuable_clone_layers", False))
    selected = policy.get("default_strategy", "hybrid_backplate_semantic_native")
    if case_meta.get("visual_backplate_value") == "minimal" and not case_meta.get("requires_visual_richness", True):
        selected = "native_shape_reconstruction_baseline"
    if case_meta.get("request_clone_substitution") and clone_allowed:
        selected = "clone_semantic_substitution"
    if selected in {"raster_page_baseline", "text_lift_overlay_baseline"}:
        selected = "hybrid_backplate_semantic_native"
    return {
        "schema_name": "strategy_selection_report",
        "status": "passed",
        "case_id": case_meta.get("case_id"),
        "selected_strategy": selected,
        "default_strategy": policy.get("default_strategy"),
        "clone_semantic_substitution_allowed": clone_allowed,
        "forbidden_strategies": policy.get("forbidden_product_strategies", ["raster_page_baseline"]),
        "raster_page_baseline_used": False,
        "full_slide_reference_background_allowed": False,
        "canva_parity_claimed": False,
    }
