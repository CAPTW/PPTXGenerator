"""E06 reclassification for the layout contract precision gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


RECLASSIFICATION_DECISION = "E06_RECLASSIFIED_BASELINE_PASS_LAYOUT_CONTRACT_REQUIRED_BEFORE_PROMOTION"


def build_e06_reclassification_report(e06_root: Path) -> dict[str, Any]:
    """Reclassify E06 as a baseline pass that still needs layout contracts."""

    report = _read_json(e06_root / "e06_controlled_product_baseline_review_report.json")
    summary = _read_json(e06_root / "e06_decision_summary.json")
    original_decision = report.get("decision") or summary.get("decision")
    checks = {
        "e06_decision_passed": original_decision == "E06_PASS_START_E07_BASELINE_PROMOTION_REVIEW",
        "source_bound_integrity_passed": report.get("source_citation_slot_binding_status") == "passed",
        "editability_passed": report.get("semantic_editability_verdict") == "passed",
        "icon_system_passed": report.get("icon_system_verdict") == "passed",
        "no_semantic_raster": int(report.get("semantic_raster_violation_count", 0)) == 0,
        "no_full_slide_raster": int(report.get("full_slide_raster_count", 0)) == 0,
        "no_screenshot_slide": int(report.get("screenshot_slide_count", 0)) == 0,
        "protected_artifacts_unchanged": bool(report.get("protected_artifacts_unchanged", False)),
    }
    return {
        "schema_name": "e06_reclassification_report",
        "decision": RECLASSIFICATION_DECISION,
        "original_decision": original_decision,
        "e06_product_baseline_status": "PASS" if checks["e06_decision_passed"] else "NOT_PROVEN",
        "e06_source_bound_integrity_status": "PASS" if checks["source_bound_integrity_passed"] else "NOT_PROVEN",
        "e06_editability_status": "PASS" if checks["editability_passed"] else "NOT_PROVEN",
        "e06_icon_system_status": "PASS" if checks["icon_system_passed"] else "NOT_PROVEN",
        "e06_coordinate_contract_status": "MISSING",
        "e06_html_preview_workbench_status": "MISSING",
        "e07_unlock_status": "REVOKED_PENDING_E06_1",
        "broad_canva_parity_claimed": False,
        "checks": checks,
        "status": "passed" if all(checks.values()) else "blocked",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
