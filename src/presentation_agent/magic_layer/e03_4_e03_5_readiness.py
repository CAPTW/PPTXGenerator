"""E03.5 readiness and v7 icon retrieval policy."""

from __future__ import annotations

from typing import Any


PASS_DECISION = "E03_4_PASS_START_E03_5_BATCH_OBJECT_PLACEMENT_WITH_ICON_V7"


def build_icon_retrieval_policy_v7() -> dict[str, Any]:
    return {
        "schema_name": "icon_retrieval_policy_v7",
        "status": "passed",
        "retrieval_order": [
            "curated_v7_exact_role_match",
            "curated_v7_alias_match_if_role_family_compatible",
            "shape_equivalent_observed_crop_match",
            "authored_svg_from_approved_role_plan",
            "blocker",
        ],
        "forbidden": [
            "generic_plus_fallback",
            "quarantined_svg",
            "contaminated_crop",
            "role_only_weak_substitute",
            "raster_fallback",
        ],
        "semantic_raster_icon_count": 0,
    }


def build_e03_5_readiness_report(
    *,
    curated_manifest: dict[str, Any],
    coverage: dict[str, Any],
    distinctiveness: dict[str, Any],
    legibility: dict[str, Any],
    fixture: dict[str, Any],
    policy: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    unresolved_p0 = int(coverage.get("unresolved_p0_count", curated_manifest.get("unresolved_p0_count", 0)) or 0)
    unresolved_p1 = int(coverage.get("unresolved_p1_count", curated_manifest.get("unresolved_p1_count", 0)) or 0)
    generic_placeholder_p0 = int(coverage.get("generic_placeholder_p0_count", curated_manifest.get("generic_placeholder_p0_count", 0)) or 0)
    semantic_raster_icon_count = int(coverage.get("semantic_raster_icon_count", curated_manifest.get("semantic_raster_icon_count", 0)) or 0)
    checks = {
        "curated_v7_exists": curated_manifest.get("status") == "passed" and int(curated_manifest.get("role_count", 0)) >= 66,
        "all_p0_covered": unresolved_p0 == 0,
        "p1_coverage_acceptable": unresolved_p1 == 0,
        "no_generic_placeholder_p0": generic_placeholder_p0 == 0,
        "no_semantic_raster_icon": semantic_raster_icon_count == 0,
        "distinctiveness_passed": distinctiveness.get("status") == "passed",
        "legibility_passed": legibility.get("status") == "passed",
        "fixture_rendered": bool(fixture.get("fixture_render_exists")),
        "policy_exists": policy.get("status") == "passed",
        "protected_artifacts_unchanged": protected_unchanged,
    }
    passed = all(checks.values())
    if passed:
        decision = PASS_DECISION
    elif semantic_raster_icon_count:
        decision = "E03_4_FAIL_SEMANTIC_RASTER_ICON_POLICY"
    elif unresolved_p0 or unresolved_p1:
        decision = "E03_4_PATCH_ICON_ROLE_COVERAGE_REQUIRED"
    elif generic_placeholder_p0 or distinctiveness.get("status") != "passed":
        decision = "E03_4_PATCH_ICON_DISTINCTIVENESS_REQUIRED"
    else:
        decision = "E03_4_PATCH_MANUAL_SVG_AUTHORING_REQUIRED"
    return {
        "schema_name": "e03_5_readiness_report",
        "status": "passed" if passed else "blocked",
        "decision": decision,
        "e03_5_unlocked": passed,
        "e04_status": "LOCKED",
        "unresolved_p0_count": unresolved_p0,
        "unresolved_p1_count": unresolved_p1,
        "generic_placeholder_p0_count": generic_placeholder_p0,
        "semantic_raster_icon_count": semantic_raster_icon_count,
        "protected_artifacts_unchanged": protected_unchanged,
        "checks": checks,
    }
