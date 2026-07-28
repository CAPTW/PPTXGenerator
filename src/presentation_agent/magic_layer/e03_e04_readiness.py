"""E04 readiness after E03 16-archetype pass."""

from __future__ import annotations

from typing import Any

from .e03_16_orchestrator import ARCHETYPES


def build_e04_readiness_report(archetype_gates: dict[str, dict[str, Any]], rhythm_report: dict[str, Any], *, pack_rendered: bool, protected_unchanged: bool) -> dict[str, Any]:
    all_pass = all(archetype_gates.get(archetype, {}).get("status") == "passed" for archetype in ARCHETYPES)
    critical = sum(len(archetype_gates.get(archetype, {}).get("critical_blockers", [])) for archetype in ARCHETYPES) + len(rhythm_report.get("critical_blockers", []))
    high = sum(len(archetype_gates.get(archetype, {}).get("high_product_risks", [])) for archetype in ARCHETYPES)
    semantic = sum(int(archetype_gates.get(archetype, {}).get("semantic_raster_violation_count", 0)) for archetype in ARCHETYPES)
    full_slide = sum(int(archetype_gates.get(archetype, {}).get("full_slide_raster_count", 0)) for archetype in ARCHETYPES)
    screenshot = sum(int(archetype_gates.get(archetype, {}).get("screenshot_slide_count", 0)) for archetype in ARCHETYPES)
    unknown = sum(int(archetype_gates.get(archetype, {}).get("unknown_content_bearing_layer_count", 0)) for archetype in ARCHETYPES)
    ready = all_pass and pack_rendered and rhythm_report.get("status") == "passed" and protected_unchanged and critical == 0 and high == 0 and semantic == 0 and full_slide == 0 and screenshot == 0 and unknown == 0
    return {
        "schema_name": "e04_readiness_report",
        "status": "passed" if ready else "locked",
        "decision": "E04_READY_START_SOURCE_BOUND_SMALL_DECK_WITH_16_MAGIC_LAYER_PLUS_PACK" if ready else "E04_LOCKED_PENDING_E03_PATCH",
        "e04_unlocked": ready,
        "all_16_archetypes_passed": all_pass,
        "candidate_pack_rendered_16_of_16": pack_rendered,
        "visual_fidelity_gate_passed": all_pass,
        "visual_rhythm_gate_passed": rhythm_report.get("status") == "passed",
        "critical_blocker_count": critical,
        "high_product_risk_count": high,
        "semantic_raster_violation_count": semantic,
        "full_slide_raster_count": full_slide,
        "screenshot_slide_count": screenshot,
        "unknown_content_bearing_layer_count": unknown,
        "protected_artifacts_unchanged": protected_unchanged,
        "broad_canva_parity_claimed": False,
        "next_stage": "E04_SOURCE_BOUND_SMALL_DECK_WITH_16_MAGIC_LAYER_PLUS_PACK" if ready else "E03_PATCH",
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
    }
