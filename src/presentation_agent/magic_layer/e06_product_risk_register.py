"""Product risk register for E06."""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_e06_product_risk_register(*, dense_audit: dict[str, Any], editability_audit: dict[str, Any], visual_rhythm_audit: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    risks = []
    if dense_audit.get("status") == "passed":
        risks.append(
            {
                "risk_id": "E06-RISK-001",
                "risk_level": "medium_polish",
                "area": "dense_slide_readability",
                "issue": "Slides 11 and 14 are baseline-ready but should be rechecked during promotion because they remain dense source-bound tables.",
                "blocks_baseline_candidate": False,
            }
        )
    else:
        risks.append(
            {
                "risk_id": "E06-RISK-001",
                "risk_level": "high_product_risk",
                "area": "dense_slide_readability",
                "issue": "Dense slide readability did not pass E06 audit.",
                "blocks_baseline_candidate": True,
            }
        )
    if editability_audit.get("editable_shape_chart_count", 0) or editability_audit.get("editable_shape_grid_table_count", 0):
        risks.append(
            {
                "risk_id": "E06-RISK-002",
                "risk_level": "medium_polish",
                "area": "chart_table_editability",
                "issue": "Charts/tables are editable shape components rather than native Office chart/table graphicFrames; keep terminology explicit in promotion review.",
                "blocks_baseline_candidate": False,
            }
        )
    if visual_rhythm_audit.get("status") == "passed":
        risks.append(
            {
                "risk_id": "E06-RISK-003",
                "risk_level": "low_polish",
                "area": "visual_rhythm",
                "issue": "Dark/teal visual system is coherent but should be monitored for monotony before scaleout.",
                "blocks_baseline_candidate": False,
            }
        )
    counts = Counter(risk["risk_level"] for risk in risks)
    register = {
        "schema_name": "e06_product_risk_register",
        "status": "passed" if counts.get("critical_blocker", 0) == 0 and counts.get("high_product_risk", 0) == 0 and counts.get("medium_polish", 0) <= 3 else "patch_required",
        "critical_blocker_count": counts.get("critical_blocker", 0),
        "high_product_risk_count": counts.get("high_product_risk", 0),
        "medium_polish_count": counts.get("medium_polish", 0),
        "low_polish_count": counts.get("low_polish", 0),
        "risks": risks,
    }
    patch_items = [
        {
            "patch_id": risk["risk_id"].replace("RISK", "PATCH"),
            "severity": risk["risk_level"],
            "issue": risk["issue"],
            "recommended_action": "Carry into E07 promotion review checklist.",
            "blocker_for_e07": risk["blocks_baseline_candidate"],
        }
        for risk in risks
        if risk["blocks_baseline_candidate"]
    ]
    patch_queue = {
        "schema_name": "e06_patch_queue",
        "status": "empty" if not patch_items else "open",
        "item_count": len(patch_items),
        "items": patch_items,
    }
    return register, patch_queue

