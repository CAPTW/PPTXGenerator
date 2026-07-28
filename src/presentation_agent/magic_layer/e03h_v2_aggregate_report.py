"""Aggregate reporting helpers for E03H-V2."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_e03h_v2_final_decision(
    *,
    aggregate_status: str,
    protected_ok: bool,
    pack_exists: bool,
    diversity_pass: bool,
) -> dict[str, Any]:
    if not protected_ok:
        decision = "E03H_V2_FAIL_PROTECTED_ARTIFACTS"
        status = "failed"
        reason = "Protected canonical artifact verification failed."
    elif aggregate_status == "passed" and pack_exists and diversity_pass:
        decision = "E03H_V2_PASS_READY_FOR_E04H_V2_SOURCE_BOUND_SMALL_DECK"
        status = "passed"
        reason = "Core 12 reference pack passed repaired Canva+ hybrid conversion gates."
    else:
        decision = "E03H_V2_FAIL_BASELINE_SHORTCUT_REMAINS"
        status = "patch_required"
        reason = "Reference pack gate detected a remaining failure mode."
    return {
        "schema_name": "e03h_v2_final_decision",
        "status": status,
        "decision": decision,
        "reason": reason,
        "e04h_v2_unlocked": decision == "E03H_V2_PASS_READY_FOR_E04H_V2_SOURCE_BOUND_SMALL_DECK",
        "e04h_v2_started": False,
        "e05_unlocked": False,
        "e05_started": False,
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "canva_parity_claimed": False,
    }


def build_e03h_v2_manifest(final: dict[str, Any], output_folder: str, reference_count: int) -> dict[str, Any]:
    return {
        "schema_name": "e03h_v2_manifest",
        "status": final["status"],
        "decision": final["decision"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_folder": output_folder,
        "reference_count": reference_count,
        "e04h_v2_unlocked": final["e04h_v2_unlocked"],
        "e05_unlocked": False,
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "canva_parity_claimed": False,
    }


def build_readiness_reports(final: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    e04_ready = final["decision"] == "E03H_V2_PASS_READY_FOR_E04H_V2_SOURCE_BOUND_SMALL_DECK"
    e04 = {
        "schema_name": "e04h_v2_readiness_report",
        "status": "ready" if e04_ready else "locked",
        "e04h_v2_unlocked": e04_ready,
        "e04h_v2_started": False,
        "reason": "E03H-V2 reference pack passed." if e04_ready else "E03H-V2 reference pack did not pass.",
        "e05_unlocked": False,
        "canva_parity_claimed": False,
    }
    e05 = {
        "schema_name": "e05_readiness_after_e03h_v2",
        "status": "locked",
        "e05_unlocked": False,
        "e05_started": False,
        "reason": "E03H-V2 may not unlock E05; E05 remains locked.",
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "canva_parity_claimed": False,
    }
    return e04, e05
