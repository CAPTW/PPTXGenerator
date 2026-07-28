"""Registry helpers for E02H-V2 holdout cases."""

from __future__ import annotations

from typing import Any


REQUIRED_HOLDOUT_CASES = [
    "holdout_01_e01hp_maritime_checklist_regression",
    "holdout_02_process_vector_infographic",
    "holdout_03_dashboard_chart_hard",
    "holdout_04_dense_table_matrix_hard",
    "holdout_05_photo_caption_hero_hard",
    "holdout_06_light_editorial_mixed",
]


def build_holdout_case_registry(manifest: dict[str, Any]) -> dict[str, Any]:
    cases = manifest.get("cases", [])
    ids = {case.get("case_id") for case in cases}
    missing = [case_id for case_id in REQUIRED_HOLDOUT_CASES if case_id not in ids]
    passed = manifest.get("status") == "passed" and len(cases) >= 6 and not missing
    return {
        "schema_name": "holdout_case_registry",
        "status": "passed" if passed else "failed",
        "case_count": len(cases),
        "required_case_count": len(REQUIRED_HOLDOUT_CASES),
        "missing_required_cases": missing,
        "cases": cases,
        "canva_parity_claimed": False,
    }
