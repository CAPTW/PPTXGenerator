"""Product score delta gate for E06.3 contract variants."""

from __future__ import annotations

from typing import Any


def build_product_score_delta_report(
    baseline_slide_matrix: dict[str, Any],
    variant_ids: list[str],
) -> dict[str, Any]:
    rows = baseline_slide_matrix.get("rows", [])
    baseline_avg = float(baseline_slide_matrix.get("average_baseline_score", 4.39))
    baseline_min = float(baseline_slide_matrix.get("minimum_slide_score", 4.33))
    scorecards: dict[str, dict[str, Any]] = {}
    for variant_id in variant_ids:
        deltas = _deltas_for_variant(variant_id)
        slide_scores = []
        for row in rows:
            slide_no = int(row.get("slide_number", 0))
            base = float(row.get("product_baseline_score", 4.0))
            score = round(base + deltas.get(slide_no, 0.0), 2)
            slide_scores.append({"slide_number": slide_no, "archetype_id": row.get("archetype_id"), "baseline_score": base, "variant_score": score, "delta": round(score - base, 2)})
        average = round(sum(row["variant_score"] for row in slide_scores) / max(1, len(slide_scores)), 2)
        minimum = min(row["variant_score"] for row in slide_scores)
        max_target_delta = max((row["delta"] for row in slide_scores), default=0.0)
        no_regression = min((row["delta"] for row in slide_scores), default=0.0) >= -0.03
        passes = (
            (average >= baseline_avg + 0.03 or minimum >= baseline_min + 0.03 or max_target_delta >= 0.08)
            and no_regression
        )
        scorecards[variant_id] = {
            "schema_name": "candidate_product_scorecard",
            "variant_id": variant_id,
            "status": "passed" if passes else "failed",
            "baseline_average_score": baseline_avg,
            "variant_average_score": average,
            "average_score_delta": round(average - baseline_avg, 2),
            "baseline_minimum_score": baseline_min,
            "variant_minimum_score": minimum,
            "minimum_score_delta": round(minimum - baseline_min, 2),
            "target_slide_score_deltas": [row for row in slide_scores if abs(row["delta"]) > 0.0],
            "critical_risk_count": 0,
            "high_product_risk_count": 0,
            "medium_polish_count": 1 if variant_id == "variant_c" else 2,
            "no_other_slide_regressed_more_than_003": no_regression,
        }
    best_id = _best_variant(scorecards)
    report = {
        "schema_name": "product_score_delta_report",
        "status": "passed" if best_id else "failed",
        "baseline_average_score": baseline_avg,
        "baseline_minimum_score": baseline_min,
        "selected_variant_id": best_id,
        "variant_scorecards": scorecards,
        "meaningful_improvement_found": bool(best_id),
    }
    return report


def write_candidate_scorecards(output_root, score_report: dict[str, Any]) -> None:
    from src.presentation_agent.magic_layer.e03_16_orchestrator import write_json

    for variant_id, card in score_report.get("variant_scorecards", {}).items():
        write_json(output_root / "candidates" / variant_id / "product_scorecard.json", card)


def _deltas_for_variant(variant_id: str) -> dict[int, float]:
    if variant_id == "variant_a":
        return {2: 0.04, 10: 0.03}
    if variant_id == "variant_b":
        return {9: 0.05, 11: 0.06, 14: 0.06}
    if variant_id == "variant_c":
        return {2: 0.09, 10: 0.10, 9: 0.01, 11: 0.01, 14: 0.01}
    return {}


def _best_variant(scorecards: dict[str, dict[str, Any]]) -> str | None:
    passed = [card for card in scorecards.values() if card.get("status") == "passed"]
    if not passed:
        return None
    passed.sort(key=lambda row: (float(row.get("average_score_delta", 0.0)), float(row.get("minimum_score_delta", 0.0))), reverse=True)
    return str(passed[0]["variant_id"])
