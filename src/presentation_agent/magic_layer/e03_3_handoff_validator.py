"""Validate E03.2 and E03.2.4A handoffs for E03.3."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


E03_2_PASS = "E03_2_PASS_SINGLE_SLIDE_GOLDEN_START_E03_3_BATCH_OBJECT_PLACEMENT_GENERALIZATION"
ICON_PASS = "E03_2_4A_RERUN_PASS_START_E03_3_BATCH_OBJECT_PLACEMENT_GENERALIZATION"


def validate_e03_2_handoff(e03_2_root: Path) -> dict[str, Any]:
    gate_path = e03_2_root / "e03_2_canva_plus_single_slide_gate_report.json"
    summary_path = e03_2_root / "e03_2_decision_summary.json"
    missing = [gate_path.as_posix()] if not gate_path.exists() else []
    if missing:
        return {"schema_name": "e03_2_handoff_validation_report", "status": "blocked", "decision": "E03_3_BLOCKED_MISSING_HANDOFF", "missing": missing}
    gate = _read_json(gate_path)
    summary = _read_json(summary_path) if summary_path.exists() else gate
    checks = {
        "final_decision": summary.get("decision") == E03_2_PASS or gate.get("decision") == E03_2_PASS,
        "selected_archetype_visual_toc": summary.get("selected_target_archetype") == "visual_toc" or gate.get("target_archetype") == "visual_toc",
        "bbox_region_gate_passed": gate.get("bbox_region_gate_result") == "passed" or summary.get("bbox_region_gate_result") == "passed",
        "z_order_gate_passed": gate.get("z_order_gate_result") == "passed" or summary.get("z_order_gate_result") == "passed",
        "visual_gate_passed": gate.get("visual_gate_result") == "passed" or summary.get("visual_gate_result") == "passed",
        "semantic_raster_zero": int(gate.get("semantic_raster_violation_count", summary.get("semantic_raster_violations", 0))) == 0,
        "full_slide_raster_zero": int(gate.get("full_slide_raster_count", summary.get("full_slide_raster_count", 0))) == 0,
        "screenshot_slide_zero": int(gate.get("screenshot_slide_count", summary.get("screenshot_slide_count", 0))) == 0,
        "unknown_content_bearing_zero": int(gate.get("unknown_content_bearing_layer_count", summary.get("unknown_content_bearing_layers", 0))) == 0,
        "protected_artifacts_unchanged": summary.get("protected_artifacts_unchanged", gate.get("protected_artifacts_unchanged", True)) is True,
    }
    status = "passed" if all(checks.values()) else "blocked"
    return {
        "schema_name": "e03_2_handoff_validation_report",
        "status": status,
        "decision": "E03_2_HANDOFF_VALIDATED_FOR_E03_3" if status == "passed" else "E03_3_BLOCKED_MISSING_HANDOFF",
        "checks": checks,
        "e03_2_decision": summary.get("decision") or gate.get("decision"),
        "selected_archetype": summary.get("selected_target_archetype") or gate.get("target_archetype"),
    }


def validate_e03_2_4a_icon_readiness(icon_root: Path, curated_v6_root: Path) -> dict[str, Any]:
    report_path = icon_root / "e03_2_4a_rerun_report.json"
    missing = [report_path.as_posix()] if not report_path.exists() else []
    if not curated_v6_root.exists():
        missing.append(curated_v6_root.as_posix())
    if missing:
        return {"schema_name": "e03_2_4a_icon_readiness_validation_report", "status": "blocked", "decision": "E03_3_BLOCKED_MISSING_HANDOFF", "missing": missing}
    report = _read_json(report_path)
    checks = {
        "final_decision": report.get("decision") == ICON_PASS,
        "concrete_annotations_applied_19": int(report.get("annotation_mapping_count", 0)) == 19 and report.get("human_annotations_present", True) is True,
        "unresolved_p0_zero": int(report.get("unresolved_p0_count", 0)) == 0,
        "unresolved_required_p1_zero": int(report.get("unresolved_required_p1_count", 0)) == 0,
        "curated_v6_exists": curated_v6_root.exists() and int(report.get("curated_v6_role_count", 0)) > 0,
        "quarantined_svg_reused_zero": int(report.get("quarantined_svg_reused_count", 0)) == 0,
        "generic_placeholder_reused_zero": int(report.get("generic_placeholder_count", 0)) == 0,
        "semantic_raster_icon_zero": int(report.get("semantic_raster_icon_count", 0)) == 0,
    }
    status = "passed" if all(checks.values()) else "blocked"
    return {
        "schema_name": "e03_2_4a_icon_readiness_validation_report",
        "status": status,
        "decision": "E03_2_4A_ICON_READINESS_VALIDATED_FOR_E03_3" if status == "passed" else "E03_3_BLOCKED_MISSING_HANDOFF",
        "checks": checks,
        "curated_v6_root": curated_v6_root.as_posix(),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
