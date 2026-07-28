from __future__ import annotations

from typing import Any


def build_e04_readiness_report(
    *,
    archetype_pass_count: int,
    pack_report: dict[str, Any],
    icon_visibility: dict[str, Any],
    visual_fidelity: dict[str, Any],
    visual_rhythm: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "archetypes_16_pass": archetype_pass_count == 16,
        "pack_exists_and_renders_16": pack_report.get("status") == "passed" and int(pack_report.get("rendered_slide_count", 0)) == 16,
        "icon_visibility_passed": icon_visibility.get("status") == "passed",
        "semantic_raster_icon_zero": int(icon_visibility.get("semantic_raster_icon_count", 0) or 0) == 0,
        "visual_fidelity_passed": visual_fidelity.get("status") == "passed",
        "visual_rhythm_passed": visual_rhythm.get("status") == "passed",
        "protected_artifacts_unchanged": protected_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e04_readiness_report",
        "status": "passed" if passed else "blocked",
        "decision": "E04_READY_START_SOURCE_BOUND_SMALL_DECK_WITH_16_MAGIC_LAYER_PLUS_PACK" if passed else "E04_LOCKED_PENDING_E03_5_PATCH",
        "e04_unlocked": passed,
        "checks": checks,
        "broad_canva_parity_claimed": False,
    }
