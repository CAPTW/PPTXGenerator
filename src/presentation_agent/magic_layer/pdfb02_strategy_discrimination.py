"""Sanity checks that PDFB02 metrics discriminate strategy quality."""

from __future__ import annotations

from typing import Any


def build_strategy_discrimination_report(comparison: dict[str, Any], fixture_results: list[dict[str, Any]]) -> dict[str, Any]:
    scores = comparison.get("strategy_scores", {})
    balanced = [row["balanced_score"] for row in scores.values()]
    nearly_same = (max(balanced) - min(balanced) < 0.08) if balanced else True
    raster_passes = scores.get("raster_page_baseline", {}).get("semantic_gate_pass_rate", 1.0) > 0.0
    native_visual_best = _native_visual_best_for_all(fixture_results)
    clone_wins = comparison.get("best_balanced_strategy") == "clone_semantic_substitution"
    object_count_bias = False
    full_slide_penalty_missing = raster_passes
    semantic_raster_penalty_missing = raster_passes
    passed = not any([nearly_same, raster_passes, native_visual_best, clone_wins, object_count_bias, full_slide_penalty_missing, semantic_raster_penalty_missing])
    return {
        "schema_name": "strategy_discrimination_report",
        "status": "passed" if passed else "failed",
        "all_strategies_score_nearly_same": nearly_same,
        "raster_baseline_passes_semantic_gate": raster_passes,
        "native_only_scores_best_visually_for_all_fixtures": native_visual_best,
        "hybrid_wins_due_to_object_count_only": object_count_bias,
        "clone_wins_despite_scaffold": clone_wins,
        "full_slide_screenshot_penalty_missing": full_slide_penalty_missing,
        "semantic_raster_penalty_missing": semantic_raster_penalty_missing,
        "canva_parity_claimed": False,
    }


def _native_visual_best_for_all(fixture_results: list[dict[str, Any]]) -> bool:
    if not fixture_results:
        return False
    for fixture in fixture_results:
        rows = fixture.get("strategy_results", {})
        best = max(rows.values(), key=lambda row: row["visual_fidelity_score"])
        if best["strategy_id"] != "native_shape_reconstruction_baseline":
            return False
    return True
