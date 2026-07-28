from __future__ import annotations

from typing import Any


def verify_rv00_claims(*, rv00_passed: bool) -> dict[str, Any]:
    claims = [
        ("RV00 locks recovery validation planning objective.", "VERIFIED" if rv00_passed else "PARTIALLY_VERIFIED"),
        ("RV00 allows RV01 reference readiness revalidation.", "VERIFIED" if rv00_passed else "PARTIALLY_VERIFIED"),
        ("RV00 runs E03.", "CONTRADICTED"),
        ("RV00 allows direct E03 rerun.", "CONTRADICTED"),
        ("RV00 proves product PASS.", "OVERCLAIMED"),
        ("RV00 proves arbitrary Magic Layer+ robustness.", "OVERCLAIMED"),
        ("RV00 unlocks E04.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("RV00 unlocks D08.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("RV00 allows canonical promotion.", "BLOCKED_BY_POLICY"),
        ("P05/P06/C05 outputs may be promoted to golden_template_masters.pptx.", "BLOCKED_BY_POLICY"),
    ]
    return {"schema": "rv00_claim_verification_report.v1", "claims": [{"claim": claim, "status": status} for claim, status in claims], "product_pass": False}


def verify_rv01_claims(*, inventory_complete: bool, readiness_validated: bool) -> dict[str, Any]:
    claims = [
        ("RV01 inventoried E03 references.", "VERIFIED" if inventory_complete else "PARTIALLY_VERIFIED"),
        ("RV01 validated E03 reference readiness.", "VERIFIED" if readiness_validated else "PARTIALLY_VERIFIED"),
        ("RV01 generated missing references.", "CONTRADICTED"),
        ("RV01 ran E03.", "CONTRADICTED"),
        ("RV01 allows direct E03 rerun without explicit E03-RV prompt.", "CONTRADICTED"),
        ("RV01 proves product PASS.", "OVERCLAIMED"),
        ("RV01 proves arbitrary Magic Layer+ robustness.", "OVERCLAIMED"),
        ("RV01 unlocks E04.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("RV01 unlocks D08.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("RV01 allows canonical promotion.", "BLOCKED_BY_POLICY"),
    ]
    return {"schema": "rv01_claim_verification_report.v1", "claims": [{"claim": claim, "status": status} for claim, status in claims], "product_pass": False}


def verify_rv01a_claims(*, kit_created: bool, registry_patch_applied: bool) -> dict[str, Any]:
    claims = [
        ("RV01A created a manual placement kit.", "VERIFIED" if kit_created else "PARTIALLY_VERIFIED"),
        ("RV01A generated missing references.", "CONTRADICTED"),
        ("RV01A made E03 references ready.", "CONTRADICTED"),
        ("RV01A ran E03.", "CONTRADICTED"),
        ("RV01A allows direct E03 rerun.", "CONTRADICTED"),
        ("RV01A proves product PASS.", "OVERCLAIMED"),
        ("RV01A unlocks E04.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("RV01A unlocks D08.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("RV01A allows canonical promotion.", "BLOCKED_BY_POLICY"),
        ("Manual references can be validated by RV01 rerun after placement.", "VERIFIED" if kit_created and registry_patch_applied else "PARTIALLY_VERIFIED"),
    ]
    return {"schema": "rv01a_claim_verification_report.v1", "claims": [{"claim": claim, "status": status} for claim, status in claims], "product_pass": False}
