"""E04.2 handoff validation for E06."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def validate_e04_2_handoff(e04_2_root: Path) -> dict[str, Any]:
    report = _read_json(e04_2_root / "e04_2_source_bound_product_polish_report.json")
    e06 = _read_json(e04_2_root / "e06_readiness_report.json")
    residual = _read_json(e04_2_root / "e04_2_patch_queue_residual.json")
    source = _read_json(e04_2_root / "e04_2_source_binding_regression_report.json")
    citation = _read_json(e04_2_root / "e04_2_citation_binding_regression_report.json")
    slot = _read_json(e04_2_root / "e04_2_slot_binding_regression_report.json")
    icon = _read_json(e04_2_root / "e04_2_icon_visibility_regression_report.json")
    contract = _read_json(e04_2_root / "e04_2_contract_v2_report.json")
    deck = e04_2_root / "harness_v3_e04_2_source_bound_small_deck_16_product_polished.pptx"
    rendered = sorted((e04_2_root / "renders").glob("slide-*.png"))
    checks = {
        "final_decision_passed": report.get("decision") == "E04_2_PASS_START_E06_CONTROLLED_PRODUCT_BASELINE_REVIEW",
        "patched_deck_exists": deck.exists(),
        "rendered_16_of_16": int(report.get("rendered_count", 0)) == 16 or len(rendered) == 16,
        "resolved_e05_patch_queue_items_11": int(report.get("patch_queue_items_resolved", 0)) == 11,
        "residual_high_zero": int(report.get("residual_high_product_risks", 1)) == 0,
        "residual_medium_zero": int(report.get("residual_medium_polish_items", 1)) == 0,
        "average_score_min": float(report.get("average_product_score", 0)) >= 4.35,
        "minimum_slide_score_min": float(report.get("minimum_slide_score", 0)) >= 4.0,
        "target_scores_min": float(report.get("slide_09_score", 0)) >= 4.0
        and float(report.get("slide_11_score", 0)) >= 4.0
        and float(report.get("slide_14_score", 0)) >= 4.0,
        "source_citation_slot_regression_zero": source.get("source_binding_regression_count", 1) == 0
        and citation.get("citation_binding_regression_count", 1) == 0
        and slot.get("slot_binding_regression_count", 1) == 0,
        "source_citation_slot_counts": source.get("source_binding_count") == 178 and citation.get("citation_binding_count") == 178 and slot.get("slot_binding_count") == 178,
        "text_below_6pt_zero": int(report.get("text_below_6pt_count", 1)) == 0,
        "text_overflow_clipping_zero": int(report.get("text_overflow_count", 1)) == 0 and int(report.get("text_clipping_count", 1)) == 0,
        "table_density_passed": report.get("table_density_verdict") == "passed",
        "source_footer_passed": report.get("source_footer_readability_verdict") == "passed",
        "icon_visibility_passed": icon.get("status") == "passed" and report.get("icon_visibility_verdict") == "passed",
        "semantic_editability_passed": report.get("semantic_editability_verdict") == "passed",
        "contract_v2_passed": contract.get("status") == "passed",
        "semantic_raster_zero": int(report.get("semantic_raster_violation_count", 1)) == 0,
        "full_slide_raster_zero": int(report.get("full_slide_raster_count", 1)) == 0,
        "screenshot_slide_zero": int(report.get("screenshot_slide_count", 1)) == 0,
        "residual_patch_queue_empty": residual.get("status") == "empty",
        "e06_ready": e06.get("decision") == "E06_READY_START_CONTROLLED_PRODUCT_BASELINE_REVIEW",
        "protected_artifacts_unchanged": bool(report.get("protected_artifacts_unchanged", False)),
    }
    passed = all(checks.values())
    return {
        "schema_name": "e04_2_handoff_validation_report",
        "status": "passed" if passed else "blocked",
        "decision": "E06_HANDOFF_VALIDATED" if passed else "E06_BLOCKED_MISSING_E04_2_HANDOFF",
        "deck_path": deck.as_posix(),
        "rendered_count": len(rendered),
        "checks": checks,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

