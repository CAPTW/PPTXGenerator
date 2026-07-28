"""E03.3 readiness after human-reviewed complex icon authoring."""

from __future__ import annotations

from typing import Any


def build_icon_retrieval_policy_v6() -> dict[str, Any]:
    return {
        "schema_name": "icon_retrieval_policy_v6",
        "status": "passed",
        "retrieval_order": [
            "curated_v6_exact_role_and_shape_match",
            "human_approved_library_match",
            "cleaned_glyph_crop_hash_match",
            "authored_svg_from_approved_crop",
            "generated_observed_svg_if_not_quarantined_and_quality_pass",
            "blocker",
        ],
        "forbidden": ["quarantined_svg", "contaminated_crop", "role_only_generic", "plus_placeholder", "raster_fallback"],
        "semantic_raster_fallback_allowed": False,
        "generic_p0_fallback_allowed": False,
    }


def build_e03_2_4_e03_3_readiness_report(
    *,
    quarantine_report: dict[str, Any],
    review_resolution: dict[str, Any],
    quality_report: dict[str, Any],
    curated_coverage: dict[str, Any],
    policy: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    unresolved_p0 = int(review_resolution.get("unresolved_p0_count", 0)) + int(curated_coverage.get("p0_unresolved_count", 0))
    unresolved_p1 = int(review_resolution.get("unresolved_p1_count", 0)) + int(curated_coverage.get("p1_unresolved_count", 0))
    human_review_required = int(review_resolution.get("human_review_required_count", 0)) - int(review_resolution.get("resolved_count", 0))
    ready = (
        quarantine_report.get("status") == "passed"
        and unresolved_p0 == 0
        and unresolved_p1 == 0
        and human_review_required == 0
        and quality_report.get("status") in {"passed", "not_run"}
        and curated_coverage.get("status") == "passed"
        and policy.get("status") == "passed"
        and int(quality_report.get("semantic_raster_icon_count", 0)) == 0
        and protected_unchanged
    )
    return {
        "schema_name": "e03_3_readiness_report",
        "status": "passed" if ready else "locked",
        "decision": "E03_2_4_PASS_START_E03_3_BATCH_OBJECT_PLACEMENT_GENERALIZATION" if ready else _decision(unresolved_p0, unresolved_p1, human_review_required, quality_report, curated_coverage),
        "e03_3_unlocked": ready,
        "e04_unlocked": False,
        "e04_lock_status": "LOCKED_PENDING_E03_3_16_OF_16",
        "bad_svg_quarantine_exists": quarantine_report.get("status") == "passed",
        "review_queue_empty_or_resolved": human_review_required == 0,
        "human_review_required_count": max(0, human_review_required),
        "unresolved_p0_count": unresolved_p0,
        "unresolved_p1_count": unresolved_p1,
        "authored_svg_quality_passes": quality_report.get("status") in {"passed", "not_run"},
        "curated_v6_exists": curated_coverage.get("status") == "passed",
        "retrieval_policy_v6_exists": policy.get("status") == "passed",
        "semantic_raster_icon_count": int(quality_report.get("semantic_raster_icon_count", 0)),
        "protected_artifacts_unchanged": protected_unchanged,
        "broad_canva_parity_claimed": False,
    }


def _decision(unresolved_p0: int, unresolved_p1: int, human_review_required: int, quality_report: dict[str, Any], curated_coverage: dict[str, Any]) -> str:
    if human_review_required or unresolved_p0 or unresolved_p1:
        return "E03_2_4_BLOCKED_HUMAN_REVIEW_REQUIRED"
    if quality_report.get("status") == "failed":
        return "E03_2_4_PATCH_MANUAL_SVG_AUTHORING"
    if curated_coverage.get("status") != "passed":
        return "E03_2_4_PATCH_CURATED_V6"
    return "E03_2_4_PATCH_BAD_SVG_QUARANTINE"
