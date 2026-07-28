"""Reclassify E03.4 before patching PowerPoint SVG renderability."""

from __future__ import annotations

from typing import Any


DECISION = "E03_4_RECLASSIFIED_ICON_LIBRARY_STRUCTURAL_PASS_POWERPOINT_RENDERABILITY_PATCH_REQUIRED"


def reclassify_e03_4(e03_4_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e03_4_reclassification_report",
        "decision": DECISION,
        "original_decision": e03_4_report.get("decision") or e03_4_report.get("final_decision"),
        "p0_role_coverage_status": "PASS",
        "p1_role_coverage_status": "PASS",
        "curated_v7_manifest_status": "PASS",
        "svg_asset_existence_status": "PASS",
        "icon_regression_fixture_pptx_status": "EXISTS",
        "actual_powerpoint_renderability_status": "FAIL",
        "16px_visibility_status": "FAIL",
        "24px_visibility_status": "UNKNOWN_OR_FAIL_UNTIL_PROVEN",
        "32px_visibility_status": "UNKNOWN_OR_FAIL_UNTIL_PROVEN",
        "e03_5_unlock_status": "REVOKED_PENDING_E03_4_1",
        "e04_status": "LOCKED",
        "broad_canva_parity_claimed": False,
    }
