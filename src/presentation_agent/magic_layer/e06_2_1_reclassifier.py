"""Reclassify E06.2 as structural-only until style/content fidelity is proven."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DECISION = "E06_2_RECLASSIFIED_CONTRACT_COORDINATE_PASS_STYLE_CONTENT_FIDELITY_PATCH_REQUIRED"


def build_e06_2_reclassification_report(e06_2_root: Path) -> dict[str, Any]:
    report = _read_json(e06_2_root / "e06_2_contract_first_recompile_report.json")
    checks = {
        "original_decision_passed": report.get("decision") == "E06_2_PASS_START_E07_BASELINE_PROMOTION_REVIEW_WITH_CONTRACT_FIRST_COMPILE",
        "coordinate_diff_zero": int(report.get("coordinate_diff_failures", 1)) == 0,
        "object_count_present": int(report.get("objects_compiled_from_contract", 0)) > 0,
        "mutation_smoke_structural_pass": report.get("mutation_smoke_test_verdict") == "passed",
        "protected_artifacts_unchanged": bool(report.get("protected_artifacts_unchanged", False)),
    }
    return {
        "schema_name": "e06_2_reclassification_report",
        "decision": DECISION,
        "original_decision": report.get("decision"),
        "coordinate_contract_status": "STRUCTURAL_PASS" if checks["coordinate_diff_zero"] else "FAIL",
        "object_count_status": "PASS" if checks["object_count_present"] else "FAIL",
        "mutation_smoke_test_status": "STRUCTURAL_PASS" if checks["mutation_smoke_structural_pass"] else "FAIL",
        "visual_style_fidelity_status": "FAIL",
        "text_content_preservation_status": "FAIL",
        "product_quality_preservation_status": "FAIL",
        "e07_unlock_status": "REVOKED_PENDING_E06_2_1",
        "broad_canva_parity_claimed": False,
        "status": "passed" if all(checks.values()) else "blocked",
        "checks": checks,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
