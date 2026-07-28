"""Handoff validation for E04.2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def validate_e05_handoff(e05_root: Path) -> dict[str, Any]:
    report = _read_json(e05_root / "e05_source_bound_product_review_report.json")
    patch_queue = _read_json(e05_root / "e05_patch_queue.json")
    patch_plan = _read_json(e05_root / "e04_2_patch_plan.json")
    e06 = _read_json(e05_root / "e06_readiness_report.json")
    checks = {
        "final_decision_patch_required": report.get("decision") == "E05_PATCH_REQUIRED_START_E04_2_SOURCE_BOUND_PRODUCT_POLISH",
        "critical_blockers_zero": int(report.get("critical_blocker_count", 1)) == 0,
        "high_product_risks_expected": int(report.get("high_product_risk_count", -1)) == 4,
        "medium_polish_expected": int(report.get("medium_polish_count", -1)) == 7,
        "patch_queue_exists": bool(patch_queue.get("items")),
        "e04_2_patch_plan_exists": patch_plan.get("target_stage") == "E04.2_SOURCE_BOUND_PRODUCT_POLISH",
        "e06_locked_pending_e04_2": e06.get("decision") == "E06_LOCKED_PENDING_E04_2_PRODUCT_POLISH",
        "protected_artifacts_unchanged": bool(report.get("protected_artifacts_unchanged", False)),
    }
    return {
        "schema_name": "e05_handoff_validation_report",
        "status": "passed" if all(checks.values()) else "blocked",
        "decision": "E04_2_HANDOFF_VALIDATED" if all(checks.values()) else "E04_2_BLOCKED_MISSING_E05_HANDOFF",
        "checks": checks,
        "patch_queue_item_count": patch_queue.get("item_count", 0),
        "target_slides": sorted({item.get("slide_number") for item in patch_queue.get("items", []) if item.get("slide_number")}),
    }


def validate_e04_1_base(e04_1_root: Path) -> dict[str, Any]:
    report = _read_json(e04_1_root / "e04_1_icon_micro_placement_report.json")
    binding = _read_json(e04_1_root / "source_citation_binding_regression_report.json")
    contract = _read_json(e04_1_root / "contract_v2_regression_report.json")
    deck = e04_1_root / "harness_v3_e04_1_source_bound_small_deck_16_icon_micro_placed.pptx"
    rendered = sorted((e04_1_root / "renders").glob("slide-*.png"))
    checks = {
        "deck_exists": deck.exists(),
        "rendered_16_of_16": len(rendered) == 16 or int(report.get("rendered_count", 0)) == 16,
        "source_regression_zero": int(binding.get("source_binding_regression_count", 1)) == 0,
        "citation_regression_zero": int(binding.get("citation_binding_regression_count", 1)) == 0,
        "slot_regression_zero": int(binding.get("slot_binding_regression_count", 1)) == 0,
        "contract_v2_passed": contract.get("status") == "passed",
        "icon_micro_placement_passed": report.get("decision") == "E04_1_PASS_START_E05_SOURCE_BOUND_PRODUCT_REVIEW",
        "semantic_raster_zero": int(report.get("semantic_raster_icon_count", 1)) == 0,
        "full_slide_raster_zero": int(report.get("full_slide_raster_count", 0)) == 0,
        "screenshot_slide_zero": int(report.get("screenshot_slide_count", 0)) == 0,
    }
    return {
        "schema_name": "e04_1_base_deck_validation_report",
        "status": "passed" if all(checks.values()) else "blocked",
        "decision": "E04_1_BASE_VALIDATED" if all(checks.values()) else "E04_2_BLOCKED_MISSING_E04_1_BASE_DECK",
        "deck_path": deck.as_posix(),
        "rendered_count": len(rendered),
        "checks": checks,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

