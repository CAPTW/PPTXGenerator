"""E07 readiness after E06.1 layout contract precision gate."""

from __future__ import annotations

from typing import Any


PASS_DECISION = "E07_READY_START_BASELINE_PROMOTION_REVIEW_WITH_LAYOUT_CONTRACT"


def build_e07_readiness_report(
    *,
    e06_reclassification: dict[str, Any],
    contract_validation: dict[str, Any],
    html_workbench: dict[str, Any],
    coordinate_diff: dict[str, Any],
    rendered_diff: dict[str, Any],
    icon_size: dict[str, Any],
    icon_anchor: dict[str, Any],
    component_anchor: dict[str, Any],
    text_collision: dict[str, Any],
    source_footer: dict[str, Any],
    risk_register: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "e06_product_baseline_pass_remains_valid": e06_reclassification.get("status") == "passed",
        "layout_contract_exists_and_validates": contract_validation.get("status") == "passed",
        "html_workbench_created": html_workbench.get("status") == "passed",
        "pptx_coordinate_diff_passed": coordinate_diff.get("status") == "passed",
        "rendered_vs_contract_diff_passed": rendered_diff.get("status") == "passed",
        "icon_size_tokens_passed": icon_size.get("status") == "passed",
        "icon_anchors_passed": icon_anchor.get("status") == "passed",
        "component_anchors_passed": component_anchor.get("status") == "passed",
        "text_collision_passed": text_collision.get("status") == "passed",
        "source_footer_coordinates_passed": source_footer.get("status") == "passed",
        "critical_coordinate_risks_zero": risk_register.get("critical_coordinate_risk_count", 1) == 0,
        "high_coordinate_risks_zero": risk_register.get("high_coordinate_risk_count", 1) == 0,
        "protected_artifacts_unchanged": protected_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e07_readiness_report",
        "status": "passed" if passed else "locked",
        "decision": PASS_DECISION if passed else "E07_LOCKED_PENDING_E06_1_PATCH",
        "e07_unlocked": passed,
        "checks": checks,
        "next_stage": "E07_BASELINE_PROMOTION_REVIEW_WITH_LAYOUT_CONTRACT" if passed else "E06_1_PATCH",
        "d08_status": "LOCKED",
        "c11_status": "LOCKED",
        "bulk_scaleout_status": "LOCKED",
        "broad_canva_parity_claimed": False,
    }


def decision_from_e07(readiness: dict[str, Any], reports: list[dict[str, Any]]) -> str:
    if readiness.get("e07_unlocked"):
        return "E06_1_PASS_START_E07_BASELINE_PROMOTION_REVIEW_WITH_LAYOUT_CONTRACT"
    by_schema = {report.get("schema_name"): report for report in reports}
    if by_schema.get("icon_anchor_validation_report", {}).get("status") != "passed":
        return "E06_1_PATCH_ICON_ANCHOR_REQUIRED"
    if by_schema.get("pptx_vs_contract_coordinate_diff_report", {}).get("status") != "passed":
        return "E06_1_PATCH_COORDINATE_DRIFT_REQUIRED"
    if by_schema.get("html_workbench_manifest", {}).get("status") != "passed":
        return "E06_1_PATCH_HTML_WORKBENCH_REQUIRED"
    return "E06_1_PATCH_LAYOUT_CONTRACT_REQUIRED"


def build_layout_drift_risk_register(*reports: dict[str, Any]) -> dict[str, Any]:
    risks: list[dict[str, Any]] = []
    for report in reports:
        status = report.get("status")
        if status not in {"passed", "empty"}:
            risks.append(
                {
                    "risk_id": f"coordinate_risk_{len(risks)+1:02d}",
                    "risk_level": "high_product_risk",
                    "source_report": report.get("schema_name"),
                    "issue": "Coordinate/layout gate failed",
                    "recommended_action": "Patch layout contract or PPTX placement before E07.",
                }
            )
    if not risks:
        risks.append(
            {
                "risk_id": "coordinate_risk_low_01",
                "risk_level": "low_polish",
                "source_report": "layout_contract_16_slides",
                "issue": "Initial contract is derived from the E06 baseline PPTX; future compiles should invert this so JSON contract is authored before PPTX compilation.",
                "recommended_action": "Use the E06.1 contract as the non-canonical baseline source of truth for promotion review.",
            }
        )
    return {
        "schema_name": "layout_drift_risk_register",
        "status": "passed" if not any(risk["risk_level"] in {"critical_coordinate_risk", "high_product_risk"} for risk in risks) else "failed",
        "critical_coordinate_risk_count": sum(1 for risk in risks if risk["risk_level"] == "critical_coordinate_risk"),
        "high_coordinate_risk_count": sum(1 for risk in risks if risk["risk_level"] == "high_product_risk"),
        "medium_coordinate_risk_count": sum(1 for risk in risks if risk["risk_level"] == "medium_polish"),
        "low_coordinate_risk_count": sum(1 for risk in risks if risk["risk_level"] == "low_polish"),
        "risks": risks,
    }
