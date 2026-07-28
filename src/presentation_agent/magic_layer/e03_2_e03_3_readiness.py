"""E03.3 readiness after the E03.2 single-slide golden gate."""

from __future__ import annotations

from typing import Any


def build_e03_3_readiness_report(gate_report: dict[str, Any], protected_unchanged: bool) -> dict[str, Any]:
    ready = gate_report.get("status") == "passed" and protected_unchanged
    return {
        "schema_name": "e03_3_readiness_report",
        "status": "passed" if ready else "locked",
        "decision": "E03_3_READY_START_BATCH_OBJECT_PLACEMENT_GENERALIZATION" if ready else "E03_3_LOCKED_PENDING_E03_2_PATCH",
        "e03_3_unlocked": ready,
        "e04_unlocked": False,
        "e04_lock_status": "PRODUCT_LOCKED_PENDING_E03_3_16_OF_16",
        "next_stage": "E03_3_BATCH_OBJECT_PLACEMENT_GENERALIZATION" if ready else "E03_2_PATCH",
        "protected_artifacts_unchanged": protected_unchanged,
        "broad_canva_parity_claimed": False,
    }
