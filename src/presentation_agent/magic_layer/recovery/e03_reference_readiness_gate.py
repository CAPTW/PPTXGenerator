from __future__ import annotations

from typing import Any


def evaluate_e03_readiness(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid_core = [row for row in rows if row.get("group") == "core" and row.get("ready")]
    valid_expansion = [row for row in rows if row.get("group") == "expansion" and row.get("ready")]
    missing_core = [row for row in rows if row.get("group") == "core" and not row.get("ready")]
    missing_expansion = [row for row in rows if row.get("group") == "expansion" and not row.get("ready")]
    min_decision = _minimum_decision(len(valid_core), len(valid_expansion), missing_core)
    full_decision = _full_decision(len(valid_core), len(valid_expansion))
    return {
        "schema": "e03_reference_readiness_gate_report.v1",
        "valid_core_count": len(valid_core),
        "valid_expansion_count": len(valid_expansion),
        "missing_core_count": len(missing_core),
        "missing_expansion_count": len(missing_expansion),
        "minimum_12_mode": {"decision": min_decision, "ready": min_decision.startswith("E03_MINIMUM_12_MODE_READY")},
        "full_16_mode": {"decision": full_decision, "ready": full_decision.startswith("E03_FULL_16_MODE_READY")},
        "e03_direct_rerun_allowed": False,
        "explicit_e03_rv_prompt_required": True,
        "e04_d08_c11_bulk_allowed": False,
        "product_pass": False,
    }


def _minimum_decision(core: int, expansion: int, missing_core: list[dict[str, Any]]) -> str:
    if core < 4:
        return "E03_MINIMUM_12_MODE_BLOCKED_MISSING_CORE"
    if expansion < 8:
        return "E03_MINIMUM_12_MODE_BLOCKED_MISSING_EXPANSION"
    return "E03_MINIMUM_12_MODE_READY"


def _full_decision(core: int, expansion: int) -> str:
    if core < 4 or expansion < 12:
        return "E03_FULL_16_MODE_BLOCKED_MISSING_REFERENCES"
    return "E03_FULL_16_MODE_READY"
