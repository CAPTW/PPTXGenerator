from __future__ import annotations

from typing import Any


def build_boundary_reports() -> dict[str, Any]:
    scaleout = {
        "schema": "scaleout_readiness_boundary_report.v1",
        "checks": {key: {"allowed": False, "reason": "P07 readiness review does not unlock scaleout"} for key in ["E03_direct_rerun", "E04", "D08", "C11", "bulk"]},
        "product_pass": False,
    }
    source_bound = {"schema": "source_bound_readiness_boundary_report.v1", "source_bound_ready": False, "e04_allowed": False, "reason": "E03 recovery validation has not passed", "product_pass": False}
    canonical = {"schema": "canonical_promotion_boundary_report.v1", "canonical_promotion_allowed": False, "golden_template_masters_update_allowed": False, "final_deck_large_premium_update_allowed": False, "product_pass": False}
    return {"source_bound": source_bound, "scaleout": scaleout, "canonical": canonical}
