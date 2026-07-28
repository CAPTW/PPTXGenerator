"""Validate the E03.5 handoff required by E04."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .e03_16_orchestrator import read_json


PASS_DECISION = "E03_5_PASS_START_E04_SOURCE_BOUND_SMALL_DECK_WITH_16_MAGIC_LAYER_PLUS_PACK"


def validate_e03_5_handoff(e03_5_root: Path) -> dict[str, Any]:
    required = [
        e03_5_root / "e03_5_batch_object_placement_with_icon_v7_1_report.json",
        e03_5_root / "e03_5_decision_summary.json",
        e03_5_root / "harness_v3_e03_5_16_magic_layer_plus_icon_v7_1_pack.pptx",
        e03_5_root / "e04_readiness_report.json",
        e03_5_root / "renders" / "e03_5_16_candidate_pack_contact_sheet.png",
        e03_5_root / "renders" / "e03_5_icon_visibility_contact_sheet.png",
        e03_5_root / "archetypes",
    ]
    missing = [path.as_posix() for path in required if not path.exists()]
    if missing:
        return {"schema_name": "e03_5_handoff_validation_report", "status": "blocked", "decision": "E04_BLOCKED_MISSING_E03_5_HANDOFF", "missing": missing}

    report = read_json(required[0])
    summary = read_json(required[1])
    readiness = read_json(required[3])
    checks = {
        "final_decision_pass": report.get("final_decision") == PASS_DECISION or report.get("decision") == PASS_DECISION or summary.get("decision") == PASS_DECISION,
        "archetypes_16_passed": int(summary.get("archetype_pass_count", report.get("archetype_status_matrix", {}).get("passed_count", 0)) or 0) == 16,
        "candidate_pack_exists": required[2].exists(),
        "pack_rendered_16": int(report.get("pack_rendered_count", 0) or 0) == 16,
        "icon_v7_1_usage_positive": int(report.get("icon_v7_1_usage_count", 0) or 0) > 0,
        "true_svg_media_insertion_positive": int(report.get("true_svg_media_insertion_count", 0) or 0) > 0,
        "invisible_icons_zero": int(report.get("invisible_icon_count", 0) or 0) == 0,
        "blank_icon_bbox_zero": int(report.get("blank_icon_bbox_count", 0) or 0) == 0,
        "semantic_raster_icons_zero": int(report.get("raster_semantic_icon_count", 0) or 0) == 0,
        "full_slide_raster_zero": int(report.get("full_slide_raster_count", 0) or 0) == 0,
        "screenshot_slide_zero": int(report.get("screenshot_slide_count", 0) or 0) == 0,
        "unknown_content_bearing_zero": int(report.get("unknown_content_bearing_count", 0) or 0) == 0,
        "text_clipping_zero": int(report.get("text_clipping_count", 0) or 0) == 0,
        "text_overflow_zero": int(report.get("text_overflow_count", 0) or 0) == 0,
        "object_collisions_zero": int(report.get("object_collision_count", 0) or 0) == 0,
        "visual_fidelity_passed": report.get("visual_fidelity_verdict") == "passed",
        "visual_rhythm_passed": report.get("visual_rhythm_verdict") == "passed",
        "e04_ready": readiness.get("decision") == "E04_READY_START_SOURCE_BOUND_SMALL_DECK_WITH_16_MAGIC_LAYER_PLUS_PACK",
        "protected_artifacts_unchanged": bool(report.get("protected_artifacts_unchanged", True)),
    }
    passed = all(checks.values())
    return {
        "schema_name": "e03_5_handoff_validation_report",
        "status": "passed" if passed else "blocked",
        "decision": "E03_5_HANDOFF_VALIDATED_FOR_E04" if passed else "E04_BLOCKED_MISSING_E03_5_HANDOFF",
        "checks": checks,
        "missing": [],
    }
