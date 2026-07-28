from __future__ import annotations

from typing import Any


ROWS = [
    ("Governance", "A01", "M5_READY_FOR_RECOVERY_VALIDATION_PLANNING"),
    ("Protocol", "E01P", "M5_READY_FOR_RECOVERY_VALIDATION_PLANNING"),
    ("Contract", "T01", "M5_READY_FOR_RECOVERY_VALIDATION_PLANNING"),
    ("Planner", "T02", "M5_READY_FOR_RECOVERY_VALIDATION_PLANNING"),
    ("Dry-run compiler", "C01", "M4_FOUR_CORE_PASS"),
    ("Real compiler", "C02B", "M4_FOUR_CORE_PASS"),
    ("B03 validation", "B03", "M5_READY_FOR_RECOVERY_VALIDATION_PLANNING"),
    ("Render backend", "C03A_RETRY", "M4_FOUR_CORE_PASS"),
    ("B01 review", "B01", "M5_READY_FOR_RECOVERY_VALIDATION_PLANNING"),
    ("Regression fixtures", "C04", "M5_READY_FOR_RECOVERY_VALIDATION_PLANNING"),
    ("Single real-reference sample", "P04", "M4_FOUR_CORE_PASS"),
    ("Four-core regression", "P05", "M5_READY_FOR_RECOVERY_VALIDATION_PLANNING"),
    ("Aggregate review pack", "P06", "M5_READY_FOR_RECOVERY_VALIDATION_PLANNING"),
    ("Native component hardening", "C05", "M5_READY_FOR_RECOVERY_VALIDATION_PLANNING"),
    ("Claim/scaleout guard", "A01", "M5_READY_FOR_RECOVERY_VALIDATION_PLANNING"),
]


def build_controlled_ladder_maturity_matrix(inventory: dict[str, Any]) -> dict[str, Any]:
    stages = inventory.get("stages", {})
    rows = []
    for area, stage, maturity in ROWS:
        passed = stages.get(stage, {}).get("passed_or_limited")
        rows.append({
            "area": area,
            "evidence_stage": stage,
            "current_status": "PASS_WITH_LIMITATIONS" if passed else "INSUFFICIENT_EVIDENCE",
            "maturity_level": maturity if passed else "M2_VALIDATOR_EXISTS",
            "target_for_now": "M5_READY_FOR_RECOVERY_VALIDATION_PLANNING",
            "blocking_gaps": [] if passed else ["missing or failed evidence"],
            "limitations": ["not product ready", "controlled evidence only"],
            "next_action": "RV00 planning" if passed else "C06 patch",
        })
    return {"schema": "controlled_ladder_maturity_matrix.v1", "rows": rows, "product_maturity_level": "BELOW_M6_PRODUCT_READY", "product_pass": False}
