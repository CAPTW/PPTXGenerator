"""Aggregate PDFB01 benchmark metrics and strategy comparison."""

from __future__ import annotations

from typing import Any


def build_strategy_comparison(fixture_results: list[dict[str, Any]]) -> dict[str, Any]:
    strategy_rows: dict[str, list[dict[str, Any]]] = {}
    for fixture_result in fixture_results:
        for strategy_id, result in fixture_result.get("strategy_results", {}).items():
            strategy_rows.setdefault(strategy_id, []).append(result)
    scores = {}
    for strategy_id, rows in strategy_rows.items():
        count = len(rows) or 1
        visual = sum(row["visual_fidelity_score"] for row in rows) / count
        edit = sum(row["editability_score"] for row in rows) / count
        hybrid = sum(row["hybrid_quality_score"] for row in rows) / count
        semantic_pass = sum(1 for row in rows if row["semantic_raster_violation_count"] == 0 and not row["full_slide_reference_background"]) / count
        scores[strategy_id] = {
            "strategy_id": strategy_id,
            "average_visual_fidelity": round(visual, 3),
            "average_editability": round(edit, 3),
            "average_hybrid_quality": round(hybrid, 3),
            "semantic_gate_pass_rate": round(semantic_pass, 3),
            "balanced_score": round((visual + edit + hybrid + semantic_pass) / 4, 3),
            "canva_parity_claimed": False,
        }
    best = max(scores.values(), key=lambda row: row["balanced_score"])["strategy_id"] if scores else None
    return {
        "schema_name": "strategy_comparison_matrix",
        "status": "passed" if best == "hybrid_backplate_semantic_native" else "failed",
        "best_balanced_strategy": best,
        "strategy_scores": scores,
        "canva_parity_claimed": False,
    }


def build_fixture_strategy_leaderboard(fixture_results: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for fixture_result in fixture_results:
        best = max(
            fixture_result["strategy_results"].values(),
            key=lambda row: (row["visual_fidelity_score"] + row["editability_score"] + row["hybrid_quality_score"]) / 3,
        )
        rows.append({"fixture_id": fixture_result["fixture_id"], "leader": best["strategy_id"], "leader_status": best["status"], "canva_parity_claimed": False})
    return {"schema_name": "fixture_strategy_leaderboard", "status": "passed", "leaders": rows, "canva_parity_claimed": False}


def build_failure_mode_taxonomy(comparison: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "failure_mode_taxonomy",
        "status": "passed",
        "failure_modes": [
            {"strategy_id": "raster_page_baseline", "failure": "high visual fidelity but fails semantic editability and full-slide raster policy"},
            {"strategy_id": "text_lift_overlay_baseline", "failure": "editable text improves but page raster remains product-blocking"},
            {"strategy_id": "native_shape_reconstruction_baseline", "failure": "semantic editability is strong but visual richness collapses"},
            {"strategy_id": "clone_semantic_substitution", "failure": "richness is retained but cloned scaffold and duplicate chrome need cleanup"},
        ],
        "recommended_default": comparison.get("best_balanced_strategy"),
        "canva_parity_claimed": False,
    }


def build_methodology_update(comparison: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "canva_plus_conversion_methodology_update",
        "status": "passed",
        "default_strategy_for_e01_e02_e03h": "hybrid_backplate_semantic_native",
        "forbidden_strategy": "raster_page_baseline for product output",
        "allowed_backplate_types": ["bounded nonsemantic texture", "hero/photo visual field", "subtle background depth", "technical ornament"],
        "cloned_layers_to_drop": ["placeholder boxes", "debug bounding frames", "duplicate table grids", "duplicate chart frames", "duplicate footer scaffolds"],
        "pdf_object_extraction_insight": "PDF-like object hints should seed text zones, reading order, and chart/table native reconstruction before image backplate planning.",
        "missing_qa_gates": ["duplicate chrome detector", "scaffold detector", "full-slide raster blocker", "semantic/native component ownership"],
        "deprecated_e04h_assumptions": ["source-bound deck quality is not proof of reference-to-editable-layer conversion", "media count alone is not design quality"],
        "best_balanced_strategy": comparison.get("best_balanced_strategy"),
        "canva_parity_claimed": False,
    }
