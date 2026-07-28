"""E03.3 readiness after complex icon vectorization."""

from __future__ import annotations

from typing import Any


def build_e03_2_3_e03_3_readiness_report(
    *,
    false_positive_report: dict[str, Any],
    complexity_report: dict[str, Any],
    quality_report: dict[str, Any],
    review_queue: dict[str, Any],
    curated_coverage: dict[str, Any],
    retrieval_policy: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    resolution = review_queue.get("resolution_report", {})
    unresolved_p0 = int(resolution.get("unresolved_p0_count", 0)) + int(curated_coverage.get("p0_unresolved_count", 0))
    unresolved_p1 = int(resolution.get("unresolved_p1_count", 0)) + int(curated_coverage.get("p1_unresolved_count", 0))
    ready = (
        false_positive_report.get("status") == "passed"
        and complexity_report.get("status") == "passed"
        and quality_report.get("status") == "passed"
        and unresolved_p0 == 0
        and unresolved_p1 == 0
        and review_queue.get("human_review_required_count", 0) == 0
        and quality_report.get("semantic_raster_icon_count", 0) == 0
        and curated_coverage.get("status") == "passed"
        and retrieval_policy.get("status") == "passed"
        and protected_unchanged
    )
    return {
        "schema_name": "e03_3_readiness_report",
        "status": "passed" if ready else "locked",
        "decision": "E03_2_3_PASS_START_E03_3_BATCH_OBJECT_PLACEMENT_GENERALIZATION" if ready else _decision(unresolved_p0, unresolved_p1, review_queue, quality_report),
        "e03_3_unlocked": ready,
        "e04_unlocked": False,
        "e04_lock_status": "LOCKED_PENDING_E03_3_16_OF_16",
        "false_positive_filter_v2_completed": false_positive_report.get("status") == "passed",
        "complex_icon_complexity_report_exists": complexity_report.get("status") == "passed",
        "approved_complex_svg_quality_passed": quality_report.get("status") == "passed",
        "curated_v5_exists": curated_coverage.get("status") == "passed",
        "retrieval_policy_v5_exists": retrieval_policy.get("status") == "passed",
        "human_review_required_count": review_queue.get("human_review_required_count", 0),
        "unresolved_p0_count": unresolved_p0,
        "unresolved_p1_count": unresolved_p1,
        "semantic_raster_icon_count": quality_report.get("semantic_raster_icon_count", 0),
        "protected_artifacts_unchanged": protected_unchanged,
        "broad_canva_parity_claimed": False,
    }


def _decision(unresolved_p0: int, unresolved_p1: int, review_queue: dict[str, Any], quality_report: dict[str, Any]) -> str:
    if review_queue.get("human_review_required_count", 0) or unresolved_p0 or unresolved_p1:
        return "E03_2_3_BLOCKED_HUMAN_REVIEW_REQUIRED"
    if quality_report.get("status") != "passed":
        return "E03_2_3_PATCH_COMPLEX_VECTOR_TRACE"
    return "E03_2_3_PATCH_FALSE_POSITIVE_FILTER"
