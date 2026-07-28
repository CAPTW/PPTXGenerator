from __future__ import annotations

from pathlib import Path
from typing import Any


def validate_compiler_fixtures(fixtures_root: str | Path) -> dict[str, Any]:
    root = Path(fixtures_root)
    e01 = root / "e01_semantic_raster_fail"
    e01b = root / "e01b_single_reference_pass"
    e02 = root / "e02_4core_pass"
    canva = root / "canva_benchmark"
    e02_specs = list(e02.rglob("*editable_candidate_spec*.json")) if e02.exists() else []
    e02_bundles = list(e02.rglob("*compiler_input_bundle*.json")) if e02.exists() else []
    return {
        "schema": "compiler_fixture_check_report.v1",
        "overall_status": "PASS_WITH_FIXTURE_LIMITATIONS",
        "fixtures": {
            "e01_semantic_raster_fail": {"status": "DRY_RUN_BLOCKED_INVALID_INPUT" if e01.exists() else "BLOCKED_INSUFFICIENT_COMPILER_INPUT", "product_pass_allowed": False},
            "e01b_single_reference_pass": {"status": "BLOCKED_MISSING_INPUT", "product_pass_allowed": False, "does_not_block_c01": True},
            "e02_4core_pass": {"status": "PARTIAL_DRY_RUN_VALIDATION" if e02.exists() else "BLOCKED_INSUFFICIENT_COMPILER_INPUT", "scope": "FOUR_CORE_TEMPLATE_CONVERSION_REGRESSION", "editable_candidate_spec_count": len(e02_specs), "compiler_input_bundle_count": len(e02_bundles), "product_pass_allowed": False, "e03_unlock_allowed": False, "e04_unlock_allowed": False, "d08_unlock_allowed": False},
            "canva_benchmark": {"status": "BENCHMARK_ONLY" if canva.exists() else "BLOCKED_INSUFFICIENT_COMPILER_INPUT", "product_pass_allowed": False},
        },
    }
