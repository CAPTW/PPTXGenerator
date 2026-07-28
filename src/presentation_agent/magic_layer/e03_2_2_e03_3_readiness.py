"""E03.3 readiness gate after icon candidate hygiene."""

from __future__ import annotations

from typing import Any


def build_e03_2_2_e03_3_readiness_report(
    *,
    references_scanned: int,
    false_positive_report: dict[str, Any],
    glyph_manifest: dict[str, Any],
    clusters: dict[str, Any],
    human_review: dict[str, Any],
    quality_report: dict[str, Any],
    curated_coverage: dict[str, Any],
    policy: dict[str, Any],
    semantic_raster_icon_count: int,
    protected_unchanged: bool,
) -> dict[str, Any]:
    resolution = human_review.get("resolution_report", {})
    unresolved_p0 = int(curated_coverage.get("p0_unresolved_count", 0)) + int(resolution.get("unresolved_p0_count", 0))
    unresolved_p1 = int(resolution.get("unresolved_p1_count", 0))
    ready = (
        references_scanned == 16
        and false_positive_report.get("status") == "passed"
        and glyph_manifest.get("status") == "passed"
        and glyph_manifest.get("normalized_glyph_crop_count", 0) > 0
        and clusters.get("status") == "passed"
        and unresolved_p0 == 0
        and quality_report.get("status") == "passed"
        and curated_coverage.get("status") == "passed"
        and policy.get("status") == "passed"
        and semantic_raster_icon_count == 0
        and protected_unchanged
        and int(quality_report.get("blank_svg_count", 0)) == 0
        and int(quality_report.get("placeholder_svg_count", 0)) == 0
    )
    return {
        "schema_name": "e03_3_readiness_report",
        "status": "passed" if ready else "locked",
        "decision": "E03_2_2_PASS_START_E03_3_BATCH_OBJECT_PLACEMENT_GENERALIZATION" if ready else _blocked_decision(unresolved_p0, unresolved_p1, false_positive_report, quality_report),
        "e03_3_unlocked": ready,
        "e04_unlocked": False,
        "e04_lock_status": "LOCKED_PENDING_E03_3_16_OF_16",
        "references_scanned": references_scanned,
        "cleaned_icon_inventory_exists": glyph_manifest.get("status") == "passed",
        "false_positive_report_exists": false_positive_report.get("status") == "passed",
        "glyph_only_crop_manifest_exists": glyph_manifest.get("status") == "passed",
        "icon_clusters_exist": clusters.get("status") == "passed",
        "all_p0_icons_resolved": unresolved_p0 == 0,
        "unresolved_p0_count": unresolved_p0,
        "unresolved_p1_count": unresolved_p1,
        "human_review_not_pending_for_p0": int(resolution.get("pending_p0_review_count", 0)) == 0,
        "generated_svg_v2_quality_passes": quality_report.get("status") == "passed",
        "curated_v4_exists": curated_coverage.get("status") == "passed",
        "retrieval_policy_v3_exists": policy.get("status") == "passed",
        "semantic_raster_icon_count": semantic_raster_icon_count,
        "protected_artifacts_unchanged": protected_unchanged,
        "broad_canva_parity_claimed": False,
    }


def _blocked_decision(unresolved_p0: int, unresolved_p1: int, false_positive_report: dict[str, Any], quality_report: dict[str, Any]) -> str:
    if unresolved_p0 or unresolved_p1:
        return "E03_2_2_BLOCKED_HUMAN_REVIEW_REQUIRED"
    if false_positive_report.get("status") != "passed":
        return "E03_2_2_PATCH_FALSE_POSITIVE_FILTER"
    if quality_report.get("status") != "passed":
        return "E03_2_2_PATCH_SVG_TRACE_RETRY"
    return "E03_2_2_PATCH_GLYPH_SPLIT"
