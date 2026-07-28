from __future__ import annotations

from typing import Any


def verify_p02_claim(claim: str, *, import_success: bool = True) -> dict[str, Any]:
    lower = claim.lower()
    if "controlled sample imported successfully" in lower:
        return {"claim": claim, "status": "VERIFIED" if import_success else "INSUFFICIENT_EVIDENCE", "product_pass": False}
    if "product pass" in lower or "arbitrary magic layer" in lower:
        return {"claim": claim, "status": "OVERCLAIMED", "product_pass": False}
    if "unlocks e03" in lower or "unlocks e04" in lower or "unlocks d08" in lower:
        return {"claim": claim, "status": "BLOCKED_BY_SCALEOUT_LOCK", "product_pass": False}
    if "promoted to golden_template_masters" in lower or "golden_template_masters" in lower:
        return {"claim": claim, "status": "BLOCKED_BY_POLICY", "product_pass": False}
    if "render can be used as reference image" in lower:
        return {"claim": claim, "status": "CONTRADICTED", "product_pass": False}
    return {"claim": claim, "status": "INCONCLUSIVE", "product_pass": False}


def build_boundary_report() -> dict[str, Any]:
    return {
        "schema": "controlled_sample_boundary_report.v1",
        "controlled_sample_chain_passed_with_limitations": True,
        "proves_local_controlled_minimal_path": True,
        "proves_product_readiness": False,
        "proves_arbitrary_image_to_editable_conversion": False,
        "proves_e03_template_pack": False,
        "proves_source_bound_deck": False,
        "unlocks_d08_c11_bulk": False,
        "canonical_promotion_allowed": False,
        "sufficient_next_steps": ["P03 controlled replay", "C04 fixture repair"],
        "product_pass": False,
    }


def build_scaleout_lock_recheck() -> dict[str, Any]:
    stages = {
        "E03": "blocked unless explicit future recovery validation starts",
        "E04": "blocked because E03 has not passed",
        "D08": "blocked because E04 has not passed",
        "C11": "blocked",
        "bulk": "blocked",
        "canonical_promotion": "blocked",
    }
    return {"schema": "scaleout_lock_recheck_report.v1", "locks": {k: {"allowed": False, "status": "BLOCKED_BY_SCALEOUT_LOCK", "reason": v} for k, v in stages.items()}, "product_pass": False}
