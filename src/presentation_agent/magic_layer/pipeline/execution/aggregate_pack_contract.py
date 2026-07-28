from __future__ import annotations

from typing import Any

from .aggregate_scope_guard import ARCHETYPES


def build_aggregate_review_pack_contract() -> dict[str, Any]:
    return {
        "schema": "p06_aggregate_review_pack_contract.v1",
        "pack_id": "p06_four_core_noncanonical_review_pack",
        "pack_type": "NONCANONICAL_REGRESSION_REVIEW_PACK",
        "slide_count": 4,
        "slide_order": ARCHETYPES,
        "source_stage": "P05",
        "product_pass": False,
        "canonical_promotion_allowed": False,
        "e03_readiness_claim_allowed": False,
        "source_bound_claim_allowed": False,
        "scaleout_allowed": False,
        "forbidden": [
            "P05 render PNGs as slide content",
            "contact sheet as slide content",
            "full-slide raster",
            "golden_template_masters.pptx overwrite",
            "source-bound deck",
        ],
    }
