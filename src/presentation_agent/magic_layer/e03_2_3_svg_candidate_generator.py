"""Build and score SVG candidate variants."""

from __future__ import annotations

from typing import Any


def build_candidate_svg_variant_manifest(local_trace_manifest: dict[str, Any], vision_repair_manifest: dict[str, Any]) -> dict[str, Any]:
    all_candidates = list(local_trace_manifest.get("candidates", [])) + list(vision_repair_manifest.get("candidates", []))
    all_candidates = [_with_score(candidate) for candidate in all_candidates]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for candidate in all_candidates:
        grouped.setdefault(candidate["icon_id"], []).append(candidate)
    approved = []
    rejected = []
    review = []
    for icon_id, rows in grouped.items():
        ordered = sorted(rows, key=lambda row: row.get("final_candidate_score", 0.0), reverse=True)
        best = ordered[0]
        if best.get("final_candidate_score", 0.0) >= 0.78:
            approved.append({**best, "approval_status": "approved_auto_quality_gate"})
            rejected.extend({**row, "rejection_reason": "lower_scoring_variant"} for row in ordered[1:])
        else:
            review.append({**best, "review_reason": "candidate_score_below_threshold"})
            rejected.extend({**row, "rejection_reason": "below_threshold"} for row in ordered[1:])
    return {
        "schema_name": "candidate_svg_variant_manifest",
        "status": "passed",
        "variant_count": len(all_candidates),
        "approved_candidate_count": len(approved),
        "rejected_variant_count": len(rejected),
        "review_required_count": len(review),
        "approved_candidates": approved,
        "rejected_candidates": rejected,
        "review_required_candidates": review,
        "candidates": all_candidates,
    }


def _with_score(candidate: dict[str, Any]) -> dict[str, Any]:
    if "final_candidate_score" in candidate:
        return candidate
    fields = [
        float(candidate.get("crop_similarity", 0.0)),
        float(candidate.get("simplification_quality", candidate.get("crop_similarity", 0.0))),
        float(candidate.get("small_size_legibility", 0.0)),
        float(candidate.get("semantic_preservation", 0.0)),
    ]
    return {**candidate, "final_candidate_score": round(sum(fields) / len(fields), 3)}
