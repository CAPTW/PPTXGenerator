"""E04.1 handoff validation for E05."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def validate_e04_1_handoff(e04_1_root: Path) -> dict[str, Any]:
    report = _read_json(e04_1_root / "e04_1_icon_micro_placement_report.json")
    readiness = _read_json(e04_1_root / "e05_revised_readiness_report.json")
    binding = _read_json(e04_1_root / "source_citation_binding_regression_report.json")
    contract = _read_json(e04_1_root / "contract_v2_regression_report.json")
    micro = _read_json(e04_1_root / "semantic_icon_micro_placement_ledger.json")
    deck = e04_1_root / "harness_v3_e04_1_source_bound_small_deck_16_icon_micro_placed.pptx"
    rendered = sorted((e04_1_root / "renders").glob("slide-*.png"))
    semantic_count = int(report.get("final_semantic_icon_count", micro.get("final_semantic_icon_count", 0)))
    checks = {
        "final_decision_passed": report.get("decision") == "E04_1_PASS_START_E05_SOURCE_BOUND_PRODUCT_REVIEW",
        "deck_exists": deck.exists(),
        "rendered_16_of_16": len(rendered) == 16 or int(report.get("rendered_count", 0)) == 16,
        "source_regression_zero": int(binding.get("source_binding_regression_count", 1)) == 0,
        "citation_regression_zero": int(binding.get("citation_binding_regression_count", 1)) == 0,
        "slot_regression_zero": int(binding.get("slot_binding_regression_count", 1)) == 0,
        "contract_v2_passed": contract.get("status") == "passed" and contract.get("contract_v2_status") == "passed",
        "semantic_icon_count_expected": semantic_count == int(report.get("anchored_semantic_icon_count", 0)),
        "unanchored_zero": int(report.get("unanchored_semantic_icon_count", 1)) == 0,
        "diagnostic_leakage_zero": int(report.get("qa_diagnostic_icon_count", 1)) == 0,
        "icon_text_collision_zero": int(report.get("icon_text_collision_count", 1)) == 0,
        "invisible_icon_zero": int(report.get("invisible_icon_count", 1)) == 0,
        "blank_icon_bbox_zero": int(report.get("blank_icon_bbox_count", 1)) == 0,
        "semantic_raster_icon_zero": int(report.get("semantic_raster_icon_count", 1)) == 0,
        "full_slide_raster_zero": int(report.get("full_slide_raster_count", 0)) == 0,
        "screenshot_slide_zero": int(report.get("screenshot_slide_count", 0)) == 0,
        "protected_artifacts_unchanged": bool(report.get("protected_artifacts_unchanged", False)),
        "e05_readiness_passed": readiness.get("decision") == "E05_READY_START_SOURCE_BOUND_PRODUCT_REVIEW",
    }
    passed = all(checks.values())
    return {
        "schema_name": "e04_1_handoff_validation_report",
        "status": "passed" if passed else "blocked",
        "decision": "E05_HANDOFF_VALIDATED" if passed else "E05_BLOCKED_MISSING_E04_1_HANDOFF",
        "deck_path": deck.as_posix(),
        "rendered_count": len(rendered),
        "semantic_icon_count": semantic_count,
        "checks": checks,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

