"""Revised E03 readiness after E02.1."""

from __future__ import annotations

from typing import Any

from .e02_4core_orchestrator import ARCHETYPES


def build_e03_revised_readiness_report(archetype_gates: dict[str, dict[str, Any]], *, pack_rendered: bool, protected_unchanged: bool) -> dict[str, Any]:
    all_pass = all(archetype_gates.get(archetype, {}).get("status") == "passed" for archetype in ARCHETYPES)
    critical = sum(len(archetype_gates.get(archetype, {}).get("critical_blockers", [])) for archetype in ARCHETYPES)
    high = sum(len(archetype_gates.get(archetype, {}).get("high_product_risks", [])) for archetype in ARCHETYPES)
    semantic_raster = sum(int(archetype_gates.get(archetype, {}).get("semantic_raster_violation_count", 0)) for archetype in ARCHETYPES)
    full_slide = sum(int(archetype_gates.get(archetype, {}).get("full_slide_raster_count", 0)) for archetype in ARCHETYPES)
    screenshot = sum(int(archetype_gates.get(archetype, {}).get("screenshot_slide_count", 0)) for archetype in ARCHETYPES)
    ready = all_pass and pack_rendered and protected_unchanged and critical == 0 and high == 0 and semantic_raster == 0 and full_slide == 0 and screenshot == 0
    return {
        "schema_name": "e03_revised_readiness_report",
        "status": "passed" if ready else "locked",
        "decision": "E03_READY_START_16_ARCHETYPE_MAGIC_LAYER_PLUS_TEMPLATE_PACK" if ready else "E03_LOCKED_PENDING_E02_1_PATCH",
        "e03_unlocked": ready,
        "all_4_e02_1_archetypes_passed": all_pass,
        "candidate_pack_rendered_4_of_4": pack_rendered,
        "visual_fidelity_region_level_pass": all_pass,
        "critical_blocker_count": critical,
        "high_product_risk_count": high,
        "semantic_raster_violation_count": semantic_raster,
        "full_slide_raster_count": full_slide,
        "screenshot_slide_count": screenshot,
        "protected_artifacts_unchanged": protected_unchanged,
        "broad_canva_parity_claimed": False,
        "next_stage": "E03_16_ARCHETYPE_MAGIC_LAYER_PLUS_TEMPLATE_PACK" if ready else "E02_1_PATCH",
        "source_bound_deck_generation_started": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
    }
