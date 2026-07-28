"""E04 readiness gate after E03.3 batch object placement."""

from __future__ import annotations

from typing import Any


def build_e04_readiness_report(
    *,
    archetype_status: dict[str, Any],
    visual_fidelity: dict[str, Any],
    visual_rhythm: dict[str, Any],
    totals: dict[str, int],
    pack_exists: bool,
    pack_rendered_16_of_16: bool,
    protected_unchanged: bool,
) -> dict[str, Any]:
    ready = (
        int(archetype_status.get("passed_count", 0)) == 16
        and int(archetype_status.get("failed_count", 0)) == 0
        and pack_exists
        and pack_rendered_16_of_16
        and visual_fidelity.get("status") == "passed"
        and visual_rhythm.get("status") == "passed"
        and all(int(totals.get(key, 0)) == 0 for key in ("semantic_raster_violation_count", "full_slide_raster_count", "screenshot_slide_count", "unknown_content_bearing_count", "text_clipping_count", "text_overflow_count", "object_collision_count"))
        and protected_unchanged
    )
    return {
        "schema_name": "e04_readiness_report",
        "status": "passed" if ready else "locked",
        "decision": "E04_READY_START_SOURCE_BOUND_SMALL_DECK_WITH_16_MAGIC_LAYER_PLUS_PACK" if ready else "E04_LOCKED_PENDING_E03_3_PATCH",
        "e04_unlocked": ready,
        "e03_3_pack_exists": pack_exists,
        "e03_3_pack_rendered_16_of_16": pack_rendered_16_of_16,
        "protected_artifacts_unchanged": protected_unchanged,
        "broad_canva_parity_claimed": False,
    }
