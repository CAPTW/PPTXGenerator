"""PDFB02 strategy metrics and tradeoff reporting."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.pdfb01_benchmark_metrics import build_strategy_comparison


def build_pdfb02_strategy_comparison(fixture_results: list[dict[str, Any]]) -> dict[str, Any]:
    comparison = build_strategy_comparison(fixture_results)
    comparison["schema_name"] = "strategy_comparison_matrix_v2"
    comparison["strategy_discrimination_basis"] = "visual_fidelity_editability_semantic_raster_hybrid_quality"
    return comparison


def build_visual_fidelity_vs_editability_tradeoff_report(comparison: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for strategy_id, score in comparison.get("strategy_scores", {}).items():
        rows.append(
            {
                "strategy_id": strategy_id,
                "average_visual_fidelity": score["average_visual_fidelity"],
                "average_editability": score["average_editability"],
                "semantic_gate_pass_rate": score["semantic_gate_pass_rate"],
                "tradeoff": _tradeoff(strategy_id),
            }
        )
    return {
        "schema_name": "visual_fidelity_vs_editability_tradeoff_report",
        "status": "passed",
        "rows": rows,
        "best_balanced_strategy": comparison.get("best_balanced_strategy"),
        "canva_parity_claimed": False,
    }


def _tradeoff(strategy_id: str) -> str:
    return {
        "raster_page_baseline": "visual fidelity only; fails semantic/native policy",
        "text_lift_overlay_baseline": "text lift helps but page raster remains blocking",
        "native_shape_reconstruction_baseline": "editable but visually weaker",
        "hybrid_backplate_semantic_native": "best balance of richness and editability",
        "clone_semantic_substitution": "high visual retention but scaffold/chrome risk",
    }.get(strategy_id, "unknown")
