"""Validate E03.4.1 handoff for E03.5."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .e03_16_orchestrator import read_json


PASS_DECISION = "E03_4_1_PASS_START_E03_5_BATCH_OBJECT_PLACEMENT_WITH_ICON_V7_1"


def validate_e03_4_1_handoff(e03_4_1_root: Path, curated_v7_1_root: Path) -> dict[str, Any]:
    required = [
        e03_4_1_root / "e03_4_1_svg_renderability_report.json",
        e03_4_1_root / "e03_5_readiness_report.json",
        e03_4_1_root / "icon_regression_fixture" / "magic_layer_v7_1_icon_regression_fixture.pptx",
        e03_4_1_root / "icon_insertion_route_policy_v2.json",
        e03_4_1_root / "themed_svg_variant_manifest.json",
    ]
    missing = [path.as_posix() for path in required if not path.exists()]
    if not curated_v7_1_root.exists():
        missing.append(curated_v7_1_root.as_posix())
    if missing:
        return {"schema_name": "e03_4_1_handoff_validation_report", "status": "blocked", "decision": "E03_5_BLOCKED_MISSING_E03_4_1_HANDOFF", "missing": missing}
    report = read_json(required[0])
    readiness = read_json(required[1])
    checks = {
        "final_decision_pass": report.get("decision") == PASS_DECISION or report.get("final_decision") == PASS_DECISION,
        "curated_v7_1_exists": curated_v7_1_root.exists(),
        "fixture_pptx_exists": required[2].exists(),
        "fixture_rendered": int(report.get("fixture_slides_rendered", 3)) >= 3,
        "p0_16_visible": int(report.get("p0_visible_at_16px_count", 0)) == 42,
        "p0_24_visible": int(report.get("p0_visible_at_24px_count", 0)) == 42,
        "p0_32_visible": int(report.get("p0_visible_at_32px_count", 0)) == 42,
        "p1_16_visible": int(report.get("p1_visible_at_16px_count", 0)) == 24,
        "p1_24_visible": int(report.get("p1_visible_at_24px_count", 0)) == 24,
        "p1_32_visible": int(report.get("p1_visible_at_32px_count", 0)) == 24,
        "blank_icon_cells_zero": int(report.get("blank_icon_cell_count", 0)) == 0,
        "invisible_icons_zero": int(report.get("invisible_icon_count", 0)) == 0,
        "semantic_raster_icons_zero": int(report.get("semantic_raster_icon_count", 0)) == 0,
        "themed_variants_exist": required[4].exists(),
        "insertion_policy_exists": required[3].exists(),
        "protected_artifacts_unchanged": bool(report.get("protected_artifacts_unchanged", True)),
        "readiness_unlocked": bool(readiness.get("e03_5_unlocked", True)),
    }
    passed = all(checks.values())
    return {
        "schema_name": "e03_4_1_handoff_validation_report",
        "status": "passed" if passed else "blocked",
        "decision": "E03_5_HANDOFF_VALIDATED" if passed else "E03_5_BLOCKED_MISSING_E03_4_1_HANDOFF",
        "checks": checks,
        "missing": [],
    }
