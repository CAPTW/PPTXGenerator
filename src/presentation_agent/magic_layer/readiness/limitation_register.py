from __future__ import annotations

from typing import Any


def build_limitation_closure_matrix(evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    c05_passed = str(evidence.get("C05", {}).get("decision", "")).startswith("C05_PASS")
    rows = [
        _row("legacy_protocol_normalization", "P05", "legacy E02 protocol normalization", "OPEN_NONBLOCKING", False, True, False),
        _row("native_dashboard_chart", "C05", "dashboard chart/KPI native evidence", "REDUCED" if c05_passed else "OPEN_BLOCKING", not c05_passed, True, False),
        _row("native_table_grid", "C05", "table shape-grid native evidence", "REDUCED" if c05_passed else "OPEN_BLOCKING", not c05_passed, True, False),
        _row("strict_text_overflow", "C05", "strict rendered overflow ledger still limited", "OPEN_NONBLOCKING", False, True, False),
        _row("visual_fidelity", "P06", "visual fidelity not product-grade", "OPEN_NONBLOCKING", False, True, False),
        _row("backend_limitations", "P06", "minimal backend limitations", "OPEN_NONBLOCKING", False, True, False),
        _row("not_product_pass", "P07", "product readiness remains false", "DEFERRED", False, True, True),
        _row("no_12_16_e03_pack", "P07", "12-16 E03 pack not validated in Pipeline v2", "DEFERRED", False, True, True),
    ]
    bridge_blockers = sum(1 for row in rows if row["blocks_recovery_validation_bridge"])
    return {"schema": "limitation_closure_matrix.v1", "limitations": rows, "bridge_blocking_gap_count": bridge_blockers, "product_pass": False}


def build_remaining_gap_register() -> dict[str, Any]:
    gaps = [
        ("e03_reference_readiness", "RECOVERY_VALIDATION_BRIDGE_GAP", "medium", False, True, "RV00/E03A reference readiness gate"),
        ("no_12_16_pipeline_v2_pack", "PRODUCT_READINESS_GAP", "high", False, True, "E03 recovery validation after RV00"),
        ("source_bound_not_started", "SOURCE_BOUND_GAP", "high", False, False, "E04 only after E03 pass"),
        ("strict_text_overflow_ledger", "PRODUCT_READINESS_GAP", "medium", False, False, "C06 if prioritized"),
        ("arbitrary_robustness_unproven", "PRODUCT_READINESS_GAP", "high", False, False, "future expansion"),
        ("canonical_promotion_blocked", "CANONICAL_PROMOTION_GAP", "high", False, False, "explicit promotion gate after product evidence"),
    ]
    return {"schema": "remaining_gap_register.v1", "gaps": [{"gap_id": gap[0], "category": gap[1], "severity": gap[2], "blocking_for_bridge": gap[3], "blocking_for_E03": gap[4], "recommended_next": gap[5]} for gap in gaps], "product_pass": False}


def _row(limitation_id: str, origin: str, description: str, status: str, bridge: bool, product: bool, e04: bool) -> dict[str, Any]:
    return {
        "limitation_id": limitation_id,
        "origin_stage": origin,
        "description": description,
        "status": status,
        "evidence": origin,
        "next_action": "RV00 planning" if not bridge else "C06 patch",
        "blocks_recovery_validation_bridge": bridge,
        "blocks_product_readiness": product,
        "blocks_E04_D08": e04,
    }
