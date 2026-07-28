"""E03.5 readiness after E03.4.1 PowerPoint renderability patch."""

from __future__ import annotations

from typing import Any


PASS_DECISION = "E03_4_1_PASS_START_E03_5_BATCH_OBJECT_PLACEMENT_WITH_ICON_V7_1"


def build_e03_5_readiness_report_v7_1(
    *,
    fixture_report: dict[str, Any],
    cell_visibility: dict[str, Any],
    legibility: dict[str, Any],
    contrast: dict[str, Any],
    curated_manifest: dict[str, Any],
    policy: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "fixture_v7_1_exists": fixture_report.get("status") == "passed",
        "fixture_v7_1_renders": bool(fixture_report.get("fixture_rendered")),
        "fixture_slide_count_3": int(fixture_report.get("rendered_slide_count", 0)) == 3,
        "cell_visibility_passed": cell_visibility.get("status") == "passed",
        "small_size_legibility_passed": legibility.get("status") == "passed",
        "dark_light_contrast_passed": contrast.get("status") == "passed",
        "curated_v7_1_exists": curated_manifest.get("status") == "passed" and int(curated_manifest.get("role_count", 0)) >= 66,
        "policy_exists": policy.get("status") == "passed",
        "semantic_raster_icon_count_zero": int(cell_visibility.get("semantic_raster_icon_count", 0)) == 0,
        "protected_artifacts_unchanged": protected_unchanged,
    }
    passed = all(checks.values())
    if passed:
        decision = PASS_DECISION
    elif int(cell_visibility.get("semantic_raster_icon_count", 0)) > 0:
        decision = "E03_4_1_FAIL_SEMANTIC_RASTER_ICON_POLICY"
    elif not fixture_report.get("fixture_rendered") or cell_visibility.get("status") != "passed":
        decision = "E03_4_1_FAIL_ICON_FIXTURE_RENDERABILITY"
    else:
        decision = "E03_4_1_PATCH_SVG_THEME_RENDERING_REQUIRED"
    return {
        "schema_name": "e03_5_readiness_report",
        "status": "passed" if passed else "blocked",
        "decision": decision,
        "e03_5_unlocked": passed,
        "e04_status": "LOCKED",
        "semantic_raster_icon_count": int(cell_visibility.get("semantic_raster_icon_count", 0)),
        "blank_icon_cell_count": int(cell_visibility.get("blank_icon_cell_count", 0)),
        "invisible_icon_count": int(cell_visibility.get("invisible_icon_count", 0)),
        "protected_artifacts_unchanged": protected_unchanged,
        "checks": checks,
    }
