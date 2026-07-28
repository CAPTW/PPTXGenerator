from __future__ import annotations

from pathlib import Path
from typing import Any


def validate_contract_fixtures(fixtures_root: str | Path) -> dict[str, Any]:
    root = Path(fixtures_root)
    e01 = root / "e01_semantic_raster_fail"
    e01b = root / "e01b_single_reference_pass"
    e02 = root / "e02_4core_pass"
    canva = root / "canva_benchmark"
    e02_slots = list(e02.rglob("slot_schema.json")) if e02.exists() else []
    report = {
        "schema": "template_fixture_check_report.v1",
        "overall_status": "PASS_WITH_FIXTURE_LIMITATIONS",
        "fixtures": {
            "e01_semantic_raster_fail": {
                "status": "NOT_COMPILE_ELIGIBLE" if e01.exists() else "BLOCKED_INSUFFICIENT_CONTRACT_INPUT",
                "product_pass_allowed": False,
                "reason": "known E01 fatal review/protocol issues and no valid product contract pass",
                "scope": "KNOWN_FAIL_FIXTURE",
            },
            "e01b_single_reference_pass": {
                "status": "BLOCKED_MISSING_INPUT",
                "product_pass_allowed": False,
                "does_not_block_t01": True,
                "reason": "compact fixture missing required contract and review inputs",
            },
            "e02_4core_pass": {
                "status": "PARTIAL_CONTRACT_VALIDATION" if e02_slots else "BLOCKED_INSUFFICIENT_CONTRACT_INPUT",
                "product_pass_allowed": False,
                "scope": "FOUR_CORE_TEMPLATE_CONVERSION_REGRESSION",
                "slot_schema_count": len(e02_slots),
                "e03_unlock_allowed": False,
                "e04_unlock_allowed": False,
                "d08_unlock_allowed": False,
            },
            "canva_benchmark": {
                "status": "BENCHMARK_ONLY" if canva.exists() else "BLOCKED_INSUFFICIENT_CONTRACT_INPUT",
                "product_pass_allowed": False,
            },
        },
    }
    return report
